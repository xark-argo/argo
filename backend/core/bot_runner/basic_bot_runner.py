import copy
import logging
import re
from collections.abc import AsyncIterator
from typing import Optional, Union, cast

from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from core.callback_handler.index_tool_callback_handler import (
    DatasetIndexToolCallbackHandler,
)
from core.callback_handler.logging_out_async_callback_handler import (
    LoggingOutAsyncCallbackHandler,
)
from core.entities.application_entities import (
    ApplicationGenerateEntity,
    BotOrchestrationConfigEntity,
    DatasetEntity,
    InvokeFrom,
    ModelConfigEntity,
    PromptTemplateEntity,
)
from core.features.browser_tool import BrowserTool, BrowserUrlTool
from core.features.dataset_retrieval import DatasetRetrievalFeature
from core.file.file_obj import FileVar
from core.memory.conversation_db_buffer_memory import (
    ConversationBufferDBMemory,
)
from core.prompt.prompt_template import CONTEXT, PromptTemplateParser
from core.queue.application_queue_manager import (
    ApplicationQueueManager,
    ConversationTaskStoppedError,
    PublishFrom,
)
from core.queue.entities.llm_entities import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
)
from models.conversation import Conversation, Message

logger = logging.getLogger(__name__)


class BasicApplicationRunner:
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

        hit_callback = DatasetIndexToolCallbackHandler(message.id, application_generate_entity.user_id, queue_manager)

        llm_instance = bot_orchestration_config.bot_model_config.llm_instance
        llm_instance.callbacks = [hit_callback, LoggingOutAsyncCallbackHandler()]

        memory = None
        if application_generate_entity.conversation_id:
            memory = ConversationBufferDBMemory(
                workspace_id=application_generate_entity.space_id,
                bot_id=application_generate_entity.bot_id,
                conversation_id=application_generate_entity.conversation_id,
                regen_message_id=application_generate_entity.regen_message_id,
                llm=llm_instance,
            )

        # get context from datasets
        context = await self.retrieve_dataset_context(
            space_id=application_generate_entity.space_id,
            bot_id=application_generate_entity.bot_id,
            model_config=bot_model_config,
            dataset_config=bot_orchestration_config.dataset,
            message=message,
            query=query,
            file_docs=application_generate_entity.file_docs,
            user_id=application_generate_entity.user_id,
            invoke_from=application_generate_entity.invoke_from,
            hit_callback=hit_callback,
        )

        if bot_model_config.network:
            context += self.retrieve_web_context(query)

        prompt_messages = self.get_prompt_messages(
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

        prompt_messages = cast(list, prompt_messages)

        # Invoke model
        invoke_result = llm_instance.astream(prompt_messages)

        # handle invoke result
        await self._handle_invoke_result_stream(
            invoke_result=invoke_result,
            prompt_messages=prompt_messages,
            bot_orchestration_config=bot_orchestration_config,
            queue_manager=queue_manager,
        )

    async def _handle_invoke_result_stream(
        self,
        invoke_result: AsyncIterator[BaseMessage | str],
        prompt_messages: list[BaseMessage],
        bot_orchestration_config: BotOrchestrationConfigEntity,
        queue_manager: ApplicationQueueManager,
    ) -> None:
        text = ""
        usage = LLMUsage.empty_usage()
        model = bot_orchestration_config.bot_model_config.model
        index = 0
        reasoning_started = False
        reasoning_stopped = False

        async for chunk in invoke_result:
            try:
                if isinstance(chunk, str):
                    token = chunk
                elif isinstance(chunk, BaseMessage):
                    token = ""
                    if "response_metadata" not in chunk.response_metadata:
                        usage.prompt_tokens = chunk.response_metadata.get("prompt_eval_count", 0)
                        usage.completion_tokens = chunk.response_metadata.get("eval_count", 0)

                    if "reasoning_content" in chunk.additional_kwargs:
                        reasoning_content_chunk = chunk.additional_kwargs.get("reasoning_content", "")
                        if reasoning_content_chunk:
                            if not reasoning_started:
                                token = "<think>"
                                reasoning_started = True
                            token += reasoning_content_chunk

                    if chunk.content and isinstance(chunk.content, str):
                        if reasoning_started and not reasoning_stopped:
                            token += "</think>"
                            reasoning_stopped = True
                        token += chunk.content
                else:
                    continue

                if not token:
                    continue

                await queue_manager.publish_chunk_message(
                    LLMResultChunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        delta=LLMResultChunkDelta(index=index, message=AIMessage(content=token)),
                    ),
                    PublishFrom.APPLICATION_MANAGER,
                )
                index += 1
                text += token

            except ConversationTaskStoppedError:
                break
            except AssertionError as e:
                message = str(e) + "\nModel response is None."
                raise AssertionError(message) from e
            except Exception as e:
                raise e

        if not text:
            raise AssertionError("Model generation failed. Please adjust your message content and regenerate.")

        llm_result = LLMResult(
            model=model,
            prompt_messages=prompt_messages,
            message=AIMessage(content=text),
            usage=usage,
        )

        await queue_manager.publish_message_end(llm_result=llm_result, pub_from=PublishFrom.APPLICATION_MANAGER)

    async def retrieve_dataset_context(
        self,
        space_id: str,
        bot_id: str,
        model_config: ModelConfigEntity,
        message: Message,
        file_docs: list[str],
        query: str,
        user_id: str,
        invoke_from: InvokeFrom,
        dataset_config: Optional[DatasetEntity],
        hit_callback: Optional[DatasetIndexToolCallbackHandler] = None,
        memory: Optional[BaseChatMemory] = None,
    ) -> str:
        dataset_retrieval = DatasetRetrievalFeature()

        context = []
        # if file_docs:
        # 	file_doc_context = dataset_retrieval.temp_run(file_docs, query)
        # 	if file_doc_context:
        # 		context.append(file_doc_context)

        if dataset_config and dataset_config.configs:
            dataset_context = await dataset_retrieval.retrieve(
                model_config=model_config,
                dataset=dataset_config,
                query=query,
                invoke_from=invoke_from,
                hit_callback=hit_callback,
                memory=memory,
            )
            if dataset_context:
                context.append(dataset_context)

        return "\n".join(context)

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
        prompt_messages: list[BaseMessage] = []

        if prompt_template_entity.prompt_type == PromptTemplateEntity.PromptType.SIMPLE:
            prompt = self.get_simple_prompt(
                inputs=inputs,
                pre_prompt=prompt_template_entity.simple_prompt_template,
                context=context,
            )
        else:
            prompt = self.get_advanced_prompt(
                inputs=inputs,
                advanced_prompt=prompt_template_entity.advanced_prompt_template,
                context=context,
            )
        prompt = re.sub(r"<\|.*?\|>", "", prompt)

        if prompt:
            prompt_messages.append(SystemMessage(content=prompt))

        if prologue:
            prompt_messages.append(AIMessage(content=prologue))

        if memory:
            prompt_messages.extend(memory.buffer)

        prompt_messages.append(self.get_last_user_message(query or prompt, files))

        return prompt_messages

    def get_simple_prompt(
        self,
        inputs: dict[str, str],
        pre_prompt: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        prompt = ""

        if context:
            context_prompt = copy.deepcopy(CONTEXT)
            prompt = context_prompt.replace("{{#context#}}", context)

        if pre_prompt:
            pre_prompt_template = PromptTemplateParser(template=pre_prompt)
            for name in pre_prompt_template.variable_keys:
                val = inputs.get(name, "")
                pre_prompt = pre_prompt.replace(f"{{{{{name}}}}}", str(val))
            prompt += pre_prompt

        return prompt

    def get_advanced_prompt(
        self,
        inputs: dict[str, str],
        advanced_prompt: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        if advanced_prompt:
            advanced_prompt = advanced_prompt.replace("{{#context#}}", context or "")

        if advanced_prompt:
            advanced_prompt_template = PromptTemplateParser(template=advanced_prompt)
            for name in advanced_prompt_template.variable_keys:
                val = inputs.get(name, "")
                advanced_prompt = advanced_prompt.replace(f"{{{{{name}}}}}", str(val))

        return advanced_prompt or ""

    def get_last_user_message(self, prompt: str, files: list[FileVar], name: Optional[str] = None) -> BaseMessage:
        if files:
            prompt_message_contents: list[Union[str, dict]] = [{"type": "text", "text": prompt}]
            for file in files:
                prompt_message_contents.append(file.prompt_message_content)

            prompt_message = HumanMessage(name=name, content=prompt_message_contents)
        else:
            prompt_message = HumanMessage(name=name, content=prompt)

        return prompt_message

    def retrieve_web_context(self, query: str) -> str:
        def extract_urls_and_text(text):
            url_pattern = re.compile(r"(https?://(?:www\.)?[-\w]+(?:\.\w[-\w]*)+" r"(?:/[-\w@:%_\+.~#?&//=]*)?)")
            urls = re.findall(url_pattern, text)
            cleaned_text = re.sub(url_pattern, "", text).strip()
            return urls, cleaned_text

        urls, cleaned_text = extract_urls_and_text(query)
        if urls:
            context = BrowserUrlTool().run(tool_input={"urls": urls})
            return str(context)
        else:
            context = BrowserTool().run(tool_input={"query": cleaned_text.strip()})
            return str(context)
