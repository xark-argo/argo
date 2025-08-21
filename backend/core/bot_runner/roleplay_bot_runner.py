import json
import logging
import re
from copy import deepcopy
from enum import Enum
from typing import Any, Optional, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from core.bot_runner.basic_bot_runner import BasicApplicationRunner
from core.bot_runner.roleplay_world_info import (
    ExtensionPromptRole,
    WorldInfoAnchorPosition,
    get_world_info_prompt,
    substitute_inputs,
)
from core.callback_handler.logging_out_callback_handler import (
    LoggingOutCallbackHandler,
)
from core.entities.application_entities import (
    ApplicationGenerateEntity,
    ModelConfigEntity,
    PromptTemplateEntity,
)
from core.features.tokenizer import get_token_count
from core.file.file_obj import FileVar
from core.memory.conversation_db_buffer_memory import (
    ConversationBufferDBMemory,
)
from core.model_providers import model_provider_manager
from core.model_providers.constants import CUSTOM_PROVIDER, OLLAMA_PROVIDER
from core.model_providers.manager import (
    ModelMode,
)
from core.queue.application_queue_manager import ApplicationQueueManager
from models.conversation import Conversation, Message

logger = logging.getLogger(__name__)

MAX_INJECTION_DEPTH = 1000
DEFAULT_AMOUNT_GEN = 80
STORY_PROMPT = """{{wiBefore}}
{{description}}
{{char}}'s personality: {{personality}}
Scenario: {{scenario}}
{{wiAfter}}
{{persona}}"""


class ExtensionPromptTypes(Enum):
    NONE = -1
    IN_PROMPT = 0
    IN_CHAT = 1
    BEFORE_PROMPT = 2


class RoleplayApplicationRunner(BasicApplicationRunner):
    extension_prompts: dict[str, dict[str, Any]] = {}
    depth_prompt_depth_default = 4
    chats_separator = "***\n"
    example_separator = "***\n"
    token_padding = 64
    reply_primed_tokens = 3  # every reply is primed with <|start|>assistant<|message|>

    async def run(
        self,
        application_generate_entity: ApplicationGenerateEntity,
        queue_manager: ApplicationQueueManager,
        conversation: Conversation,
        message: Message,
    ) -> None:
        bot_orchestration_config = application_generate_entity.bot_orchestration_config_entity
        bot_model_config = bot_orchestration_config.bot_model_config

        query = application_generate_entity.query
        inputs = application_generate_entity.inputs

        if "char" not in inputs or not inputs["char"]:
            inputs["char"] = application_generate_entity.bot_name

        user = inputs.get("user", "Human")
        char = inputs.get("char", "AI")

        model_mode = ModelMode.CHAT.value
        if inputs.get("model_mode", "") == ModelMode.GENERATE.value and bot_model_config.provider == OLLAMA_PROVIDER:
            model_mode = ModelMode.GENERATE.value

        bot_model_config.mode = model_mode

        prompt_method = self.get_prompt_messages
        if model_mode == ModelMode.GENERATE.value:
            prompt_method = self.get_generate_prompt_messages
            extracted_params = bot_model_config.parameters
            extracted_params["raw"] = True
            extracted_params["stop"] = [f"\n{user}:"]
            llm_instance = model_provider_manager.get_model_instance(
                provider=bot_model_config.provider, model_params=extracted_params, mode=ModelMode.GENERATE
            )
        else:
            llm_instance = bot_model_config.llm_instance

        llm_instance.callbacks = [LoggingOutCallbackHandler()]

        memory = ConversationBufferDBMemory(human_prefix=user, ai_prefix=char)
        if application_generate_entity.conversation_id:
            memory.conversation_id = application_generate_entity.conversation_id
            memory.regen_message_id = application_generate_entity.regen_message_id
            memory.llm = llm_instance

        # get context from datasets
        context = await self.retrieve_dataset_context(
            bot_id=application_generate_entity.bot_id,
            model_config=bot_model_config,
            dataset_config=bot_orchestration_config.dataset,
            message=message,
            query=query,
            file_docs=application_generate_entity.file_docs,
            user_id=application_generate_entity.user_id,
            invoke_from=application_generate_entity.invoke_from,
        )

        if bot_model_config.network:
            context += self.retrieve_web_context(query)

        prompt_messages = prompt_method(
            query=query,
            prologue=bot_model_config.prologue,
            prompt_template_entity=bot_orchestration_config.prompt_template,
            inputs=inputs,
            files=application_generate_entity.file_objs,
            conversation=conversation,
            memory=memory,
            context=context,
            model_config=bot_model_config,
        )

        # Invoke model
        invoke_result = llm_instance.astream(prompt_messages)

        # handle invoke result
        await self._handle_invoke_result_stream(
            invoke_result=invoke_result,
            prompt_messages=(
                [SystemMessage(content=prompt_messages)] if isinstance(prompt_messages, str) else prompt_messages
            ),
            bot_orchestration_config=bot_orchestration_config,
            queue_manager=queue_manager,
        )

    def get_generate_prompt_messages(
        self,
        inputs: dict[str, str],
        query: str,
        prompt_template_entity: PromptTemplateEntity,
        conversation: Conversation,
        model_config: ModelConfigEntity,
        files: list[FileVar],
        context: str,
        prologue: Optional[str] = None,
        memory: Optional[ConversationBufferDBMemory] = None,
    ) -> Union[str, list[BaseMessage]]:
        # Determine the prompt template type
        system = (
            prompt_template_entity.simple_prompt_template
            if prompt_template_entity.prompt_type == PromptTemplateEntity.PromptType.SIMPLE
            else prompt_template_entity.advanced_prompt_template
        )
        prompt_template = f"{system}\n{STORY_PROMPT}" if system else STORY_PROMPT

        messages = []
        ai_prefix = "AI"
        human_prefix = "Human"
        if memory:
            messages = deepcopy(memory.buffer)
            ai_prefix = memory.ai_prefix
            human_prefix = memory.human_prefix
        if prologue:
            content = substitute_inputs(inputs, prologue)
            messages.insert(0, AIMessage(name=ai_prefix, content=content))

        messages.append(self.get_last_user_message(query, files, human_prefix))
        max_context = self.get_max_context_size(model_config, ModelMode.GENERATE)

        # Parse extensions
        extensions = json.loads(inputs.get("character_extensions", "{}"))
        depth_prompt = extensions.get("depth_prompt", {})
        if "prompt" in depth_prompt:
            role = ExtensionPromptRole.SYSTEM.value
            if isinstance(depth_prompt.get("role"), int):
                role = depth_prompt["role"]

            self.extension_prompts["DEPTH_PROMPT"] = {
                "value": self.base_chat_replace(inputs, depth_prompt["prompt"]),
                "position": ExtensionPromptTypes.IN_CHAT.value,
                "depth": depth_prompt.get("depth", self.depth_prompt_depth_default),
                "scan": False,
                "role": role,
            }

        # Parse message examples
        mes_example = inputs.get("mes_example", "")
        mes_example = self.base_chat_replace(inputs, mes_example)
        mes_examples = self.parse_mes_examples(mes_example, ModelMode.GENERATE) if mes_example else []

        # Extract world info
        wi_messages = [self.format_message_content(msg) for msg in reversed(messages)]
        world_info_prompt = get_world_info_prompt(model_config, max_context, conversation, wi_messages, inputs)

        inputs.update(
            {
                "wiBefore": substitute_inputs(inputs, world_info_prompt.get("world_info_before")),
                "wiAfter": substitute_inputs(inputs, world_info_prompt.get("world_info_after")),
            }
        )

        for example in world_info_prompt.get("em_entries", []):
            example_message = example.get("content", "")
            if example_message:
                example_message = self.base_chat_replace(inputs, example_message)
                cleaned_example = self.parse_mes_examples(example_message, ModelMode.CHAT)
                if example.get("position") == WorldInfoAnchorPosition.Before.value:
                    mes_examples[0:0] = cleaned_example
                else:
                    mes_examples.extend(cleaned_example)

        if mes_examples:
            inputs.update(
                {
                    "mesExamples": "".join(mes_examples),
                }
            )

        for entry in world_info_prompt.get("world_info_depth", []):
            self.extension_prompts[f"customDepthWI-{entry['depth']}-{entry['role']}"] = {
                "value": "\n".join(entry["entries"]),
                "position": ExtensionPromptTypes.IN_CHAT.value,
                "depth": entry["depth"],
                "scan": False,
                "role": entry["role"],
            }

        injected_indices = self.inject_chat_messages(inputs, messages, human_prefix, ai_prefix)

        before_scenario_anchor = self.get_extension_prompt(
            ExtensionPromptTypes.BEFORE_PROMPT.value, inputs=inputs
        ).lstrip()
        after_scenario_anchor = self.get_extension_prompt(ExtensionPromptTypes.IN_PROMPT.value, inputs=inputs)

        system_prompt = self.render_story_prompt(
            inputs=inputs,
            prompt_template=prompt_template.replace("\r", ""),
            context=context,
        )
        system_prompt = self.base_chat_replace(inputs, system_prompt)

        chat_string = self.chats_separator
        last_message = self.format_message_content(AIMessage(name=ai_prefix, content=""), "")

        def get_messages_token_count():
            encode_string = "".join(
                [
                    before_scenario_anchor,
                    system_prompt,
                    after_scenario_anchor,
                    chat_string,
                    last_message,
                ]
            ).replace("\r", "")
            return get_token_count(encode_string, model_config) + self.token_padding

        token_count = get_messages_token_count()
        completed_messages: list[Optional[BaseMessage]] = [None] * len(messages)
        messages.reverse()

        for index in injected_indices:
            if index < 0 or index >= len(messages):
                continue

            item = self.format_message_content(messages[index])
            if not item:
                continue

            token_count += get_token_count(item, model_config)
            if token_count >= max_context:
                break
            chat_string += item
            completed_messages[index] = messages[index]

        for i, message in enumerate(messages):
            if completed_messages[i] is not None:
                continue

            item = self.format_message_content(message)
            if not item:
                continue

            token_count += get_token_count(item, model_config)
            if token_count >= max_context:
                break
            chat_string += item
            completed_messages[i] = message

        count_exm_add = 0
        token_count = get_messages_token_count()
        for example in mes_examples:
            token_count += get_token_count(example, model_config)
            if token_count >= max_context:
                break
            count_exm_add += 1

        mes_examples_string = ""
        if mes_examples:
            mes_examples_string = "".join(mes_examples[:count_exm_add])

        completed_messages.reverse()
        combined_prompt = "".join(
            [
                before_scenario_anchor,
                system_prompt,
                after_scenario_anchor,
                mes_examples_string,
                self.chats_separator,
                self.format_messages_content(completed_messages),
                last_message,
            ]
        ).replace("\r", "")

        return combined_prompt

    def get_prompt_messages(
        self,
        inputs: dict[str, str],
        query: str,
        prompt_template_entity: PromptTemplateEntity,
        conversation: Conversation,
        model_config: ModelConfigEntity,
        files: list[FileVar],
        context: str,
        prologue: Optional[str] = None,
        memory: Optional[ConversationBufferDBMemory] = None,
    ) -> Union[str, list[BaseMessage]]:
        # Determine the prompt template type
        main_prompt = (
            prompt_template_entity.simple_prompt_template
            if prompt_template_entity.prompt_type == PromptTemplateEntity.PromptType.SIMPLE
            else prompt_template_entity.advanced_prompt_template
        )

        if context and main_prompt:
            main_prompt = main_prompt.replace("{{#context#}}", context)

        messages = []
        ai_prefix = "AI"
        human_prefix = "Human"
        if memory:
            messages = deepcopy(memory.buffer)
            ai_prefix = memory.ai_prefix
            human_prefix = memory.human_prefix
        if prologue:
            content = substitute_inputs(inputs, prologue.replace("\r", ""))
            messages.insert(0, AIMessage(name=ai_prefix, content=content))

        messages.append(self.get_last_user_message(query, files, human_prefix))

        max_context = self.get_max_context_size(model_config, ModelMode.CHAT)

        # Parse extensions
        extensions = json.loads(inputs.get("character_extensions", "{}"))
        depth_prompt = extensions.get("depth_prompt", {})
        if "prompt" in depth_prompt:
            role = ExtensionPromptRole.SYSTEM.value
            if isinstance(depth_prompt.get("role"), int):
                role = depth_prompt["role"]

            self.extension_prompts["DEPTH_PROMPT"] = {
                "value": self.base_chat_replace(inputs, depth_prompt["prompt"]),
                "position": ExtensionPromptTypes.IN_CHAT.value,
                "depth": depth_prompt.get("depth", self.depth_prompt_depth_default),
                "scan": False,
                "role": role,
            }

        # Parse message examples
        mes_example = inputs.get("mes_example", "")
        mes_example = self.base_chat_replace(inputs, mes_example)
        mes_examples = self.parse_mes_examples(mes_example, ModelMode.CHAT) if mes_example else []

        # Extract world info
        wi_messages = [self.format_message_content(msg) for msg in reversed(messages)]
        world_info_prompt = get_world_info_prompt(model_config, max_context, conversation, wi_messages, inputs)

        for example in world_info_prompt.get("em_entries", []):
            example_message = example.get("content", "")
            if example_message:
                example_message = self.base_chat_replace(inputs, example_message)
                cleaned_example = self.parse_mes_examples(example_message, ModelMode.CHAT)
                if example.get("position") == WorldInfoAnchorPosition.Before.value:
                    mes_examples[0:0] = cleaned_example
                else:
                    mes_examples.extend(cleaned_example)

        for entry in world_info_prompt.get("world_info_depth", []):
            self.extension_prompts[f"customDepthWI-{entry['depth']}-{entry['role']}"] = {
                "value": "\n".join(entry["entries"]).replace("\r", ""),
                "position": ExtensionPromptTypes.IN_CHAT.value,
                "depth": entry["depth"],
                "scan": False,
                "role": entry["role"],
            }

        self.inject_chat_messages(inputs, messages, human_prefix, ai_prefix)

        # Process examples
        examples = [
            self.parse_example_into_individual(
                item.replace("<START>", "{Example Dialogue:}", 1).replace("\r", ""),
                human_prefix,
                ai_prefix,
            )
            for item in mes_examples
        ]

        # Substitute inputs for various sections
        main_prompt = self.base_chat_replace(inputs, main_prompt)
        wi_before = self.base_chat_replace(inputs, world_info_prompt.get("world_info_before"))
        wi_after = self.base_chat_replace(inputs, world_info_prompt.get("world_info_after"))
        char_description = self.base_chat_replace(inputs, inputs.get("description", ""))
        char_personality = self.base_chat_replace(inputs, inputs.get("personality", ""))
        scenario = self.base_chat_replace(inputs, inputs.get("scenario", ""))
        persona_description = self.base_chat_replace(inputs, inputs.get("persona", ""))
        post_history_instructions = self.base_chat_replace(inputs, inputs.get("post_history_instructions", ""))

        # Helper to add chat messages and manage token count
        chat_messages = []
        token_count = self.reply_primed_tokens
        logged_identifiers = set()

        def add_chat_message(message, identifier):
            nonlocal token_count
            if message.content:
                token_count += get_token_count(message.content, model_config)
                if token_count >= max_context:
                    if identifier not in logged_identifiers:
                        logging.warn(f"Token budget exceeded. Message: {identifier}")
                        logged_identifiers.add(identifier)
                    return
                chat_messages.append(message)

        # Add system messages
        system_messages = [
            (main_prompt, "MainPrompt"),
            (wi_before, "WorldInfoBefore"),
            (persona_description, "PersonaDescription"),
            (char_description, "CharDescription"),
            (char_personality, "CharPersonality"),
            (scenario, "Scenario"),
            (wi_after, "WorldInfoAfter"),
        ]

        for content, identifier in system_messages:
            add_chat_message(SystemMessage(content=content), identifier)

        # Add examples
        new_example_chat = SystemMessage(content="[Example Chat]")
        for dialogue in examples:
            add_chat_message(new_example_chat, "DialogueExamples")
            for prompt in dialogue:
                add_chat_message(
                    SystemMessage(name=prompt.name, content=prompt.content),
                    "DialogueExamples",
                )

        # Add chat history
        new_chat_message = SystemMessage(content="[Start a new Chat]")
        add_chat_message(new_chat_message, "ChatHistory")
        for message in messages:
            add_chat_message(message, "ChatHistory")

        # Add jailbreak
        if post_history_instructions:
            add_chat_message(
                SystemMessage(content=post_history_instructions),
                "Post-History Instructions",
            )

        return self.post_process_prompt(model_config, chat_messages, human_prefix, ai_prefix)

    def post_process_prompt(
        self,
        model_config: ModelConfigEntity,
        messages: list[BaseMessage],
        user: str,
        char: str,
    ) -> list[BaseMessage]:
        if model_config.provider.startswith(CUSTOM_PROVIDER) and model_config.model.startswith("deepseek"):
            return self.merge_messages(messages, user, char, True)
        else:
            return messages

    def merge_messages(self, messages: list[BaseMessage], user, char, strict) -> list[BaseMessage]:
        merged_messages: list[BaseMessage] = []

        for message in messages:
            if isinstance(message, SystemMessage) and message.name == "example_assistant":
                if isinstance(message.content, str) and not message.content.startswith(f"{char}: "):
                    message.content = f"{char}: {message.content}"

            if isinstance(message, SystemMessage) and message.name == "example_user":
                if isinstance(message.content, str) and not message.content.startswith(f"{user}: "):
                    message.content = f"{user}: {message.content}"

            message.name = ""

        for message in messages:
            if merged_messages and type(merged_messages[-1]) == type(message):
                if isinstance(merged_messages[-1].content, str) and isinstance(message.content, str):
                    merged_messages[-1].content += "\n\n" + message.content
            else:
                merged_messages.append(message)

        if strict:
            for i in range(len(merged_messages)):
                if i > 0 and isinstance(merged_messages[i], SystemMessage):
                    merged_messages[i] = HumanMessage(content=merged_messages[i].content)

            return self.merge_messages(merged_messages, user, char, False)

        return merged_messages

    def base_chat_replace(self, inputs, value):
        value = substitute_inputs(inputs, value)
        value = value.replace("\r", "")
        return value

    def parse_example_into_individual(self, message_example_string, user, char):
        result = []
        tmp = message_example_string.split("\n")
        cur_msg_lines: list[str] = []
        in_user = False
        in_bot = False
        bot_name = char

        def add_message(name, system_name):
            nonlocal cur_msg_lines
            parsed_msg = "\n".join(cur_msg_lines).replace(f"{name}:", "").strip()

            result.append(SystemMessage(name=system_name, content=parsed_msg))
            cur_msg_lines = []

        for i in range(1, len(tmp)):
            cur_str = tmp[i]
            if cur_str.startswith(f"{user}:"):
                in_user = True
                if in_bot:
                    add_message(bot_name, "example_assistant")
                in_bot = False
            elif cur_str.startswith(f"{char}:"):
                in_bot = True
                if in_user:
                    add_message(user, "example_user")
                in_user = False

            cur_msg_lines.append(cur_str)

        if in_user:
            add_message(user, "example_user")
        elif in_bot:
            add_message(bot_name, "example_assistant")

        return result

    def get_max_context_size(self, model_config: ModelConfigEntity, mode: ModelMode = ModelMode.GENERATE):
        max_context = model_config.parameters.get("num_ctx", 8192)

        if mode == ModelMode.GENERATE:
            return max_context - DEFAULT_AMOUNT_GEN
        elif mode == ModelMode.CHAT:
            return max_context - model_config.parameters.get("num_predict", 0)

        return max_context

    def parse_mes_examples(self, examples_str, mode: ModelMode = ModelMode.GENERATE):
        if len(examples_str) == 0 or examples_str == "<START>":
            return []

        if not examples_str.startswith("<START>"):
            examples_str = "<START>\n" + examples_str.strip()

        block_heading = "<START>\n" if mode == ModelMode.CHAT.value else self.example_separator

        split_examples = [f"{block_heading}{block.strip()}\n" for block in examples_str.split("<START>")[1:]]

        return split_examples

    def format_messages_content(self, messages: list[Union[None, BaseMessage]]) -> str:
        string_messages = []
        for m in messages:
            message = self.format_message_content(m)
            if message:
                string_messages.append(message)

        return "".join(string_messages)

    def format_message_content(self, message: Optional[BaseMessage], separator="\n") -> str:
        if not message:
            return ""

        if not isinstance(message.content, str):
            return ""

        message_string = message.content
        if message.name:
            return f"{message.name}: {message.content}{separator}"

        if len(message_string) > 0 and not message_string.endswith(separator):
            message_string += separator

        return message_string

    def inject_chat_messages(self, inputs: dict[str, str], messages: list[BaseMessage], user, char) -> list[int]:
        injected_indices: list[int] = []
        total_inserted_messages = 0
        messages.reverse()

        roles = [
            ExtensionPromptRole.SYSTEM,
            ExtensionPromptRole.USER,
            ExtensionPromptRole.ASSISTANT,
        ]

        for i in range(MAX_INJECTION_DEPTH):
            role_messages = []
            separator = "\n"

            for role in roles:
                extension_prompt = self.get_extension_prompt(
                    ExtensionPromptTypes.IN_CHAT.value, i, separator, role.value, inputs
                ).lstrip()
                if extension_prompt:
                    message: Union[HumanMessage, AIMessage, SystemMessage]
                    if role == ExtensionPromptRole.USER:
                        message = HumanMessage(name=user, content=extension_prompt)
                    elif role == ExtensionPromptRole.ASSISTANT:
                        message = AIMessage(name=char, content=extension_prompt)
                    else:
                        message = SystemMessage(content=extension_prompt)

                    role_messages.append(message)

            if role_messages:
                depth = i
                inject_idx = depth + total_inserted_messages
                messages[inject_idx:inject_idx] = role_messages
                total_inserted_messages += len(role_messages)
                injected_indices.extend(range(inject_idx, inject_idx + len(role_messages)))

        messages.reverse()
        return injected_indices

    def render_story_prompt(self, inputs: dict[str, str], prompt_template: str, context: str) -> str:
        if not prompt_template:
            return ""

        if context:
            prompt_template = prompt_template.replace("{{#context#}}", context)

        output = substitute_inputs(inputs, prompt_template)
        output = re.sub(r"^\n+", "", output)
        output = re.sub(r"^\s*\n", "", output, flags=re.MULTILINE)

        if len(output) > 0 and not output.endswith("\n"):
            output += "\n"

        return output

    def get_extension_prompt(
        self,
        position=ExtensionPromptTypes.IN_PROMPT.value,
        depth=None,
        separator="\n",
        role=None,
        inputs=None,
    ) -> str:
        if inputs is None:
            inputs = {}

        prompt_promises = [
            prompt
            for key, prompt in sorted(self.extension_prompts.items())
            if prompt["position"] == position
            and prompt.get("value")
            and (depth is None or prompt.get("depth") is None or prompt["depth"] == depth)
            and (role is None or prompt.get("role") is None or prompt["role"] == role)
        ]

        values = separator.join([prompt["value"].strip() for prompt in prompt_promises])

        if values and not values.startswith(separator):
            values = separator + values

        if values and not values.endswith(separator):
            values = values + separator

        return substitute_inputs(inputs, values)
