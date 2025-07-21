import asyncio
import logging
import threading
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Union

import ollama
from httpx import ConnectError

from core.bot_runner.agent_bot_runner import AgentBotRunner
from core.bot_runner.basic_bot_runner import BasicApplicationRunner
from core.bot_runner.generate_task_pipeline import GenerateTaskPipeline
from core.bot_runner.langgraph_agent_runner import LanggraphAgentRunner
from core.bot_runner.roleplay_bot_runner import RoleplayApplicationRunner
from core.entities.application_entities import (
    AgentEntity,
    AgentToolEntity,
    ApplicationGenerateEntity,
    BotOrchestrationConfigEntity,
    DatasetEntity,
    InvokeFrom,
    ModelConfigEntity,
    PlanningStrategy,
    PromptTemplateEntity,
)
from core.errors.errcode import Errcode
from core.file.message_file_parser import MessageFileParser
from core.i18n.translation import translation_loader
from core.model_providers import model_provider_manager
from core.model_providers.constants import OLLAMA_PROVIDER
from core.queue.application_queue_manager import (
    ApplicationQueueManager,
    ConversationTaskStoppedError,
    PublishFrom,
)
from core.tracking.client import ChatTrackingPayload, argo_tracking
from database import db
from models.bot import BotCategory, BotModelConfig, get_bot, get_model_config
from models.conversation import (
    Conversation,
    Message,
    MessageAgentThought,
    get_conversation,
    get_message,
)
from services.bot.model_config import ModelConfigService
from services.chat.util import get_file_docs


class ChatService:
    @staticmethod
    async def say(user_id: str, args: Any):
        query = args["message"]
        conversation_id = args["conversation_id"]
        bot_id = args["bot_id"]
        stream = args.get("stream", True)
        model_config = args.get("model_config", None)
        inputs = args.get("inputs", {})
        invoke_from = args.get("invoke_from", None)
        regen_message_id = args.get("regen_message_id", None)

        # get bot
        bot = get_bot(bot_id)
        if not bot:
            raise ValueError("Bot not found")

        # get conversation
        conversation = get_conversation(conversation_id) if conversation_id else None
        if conversation_id and not conversation:
            raise ValueError("Conversation not found")

        bot_model_config = get_model_config(bot.bot_model_config_id)
        if not bot_model_config:
            raise ValueError("Bot model config broken")

        if model_config:
            model_config = ModelConfigService.validate_configuration(config=model_config, bot_mode=bot.mode)
            # build new app model config
            if "model" not in args["model_config"]:
                raise ValueError("model_config.model is required")

            if "completion_params" not in args["model_config"]["model"]:
                raise ValueError("model_config.model.completion_params is required")

            bot_model_config = BotModelConfig(
                id=bot_model_config.id,
                bot_id=bot.id,
            )
            bot_model_config = bot_model_config.from_model_config_dict(model_config)

        bot_model_config_dict = bot_model_config.to_dict()

        inputs = ChatService.get_cleaned_inputs(inputs, bot_model_config)

        # parse files
        file_objs = []
        file_docs = []
        files = args.get("files", [])
        if files:
            message_file_parser = MessageFileParser(bot_id=bot_id)
            file_objs = message_file_parser.validate_and_transform_files_arg(files)
            file_docs = get_file_docs(files)
        # else:
        #     file_docs = conversation.docs if conversation else []

        # init application generate entity
        application_generate_entity = ApplicationGenerateEntity(
            task_id=str(uuid.uuid4()),
            bot_id=bot_id,
            bot_name=bot.name,
            bot_category=bot.category or BotCategory.ASSISTANT.value,
            bot_model_config_id=bot_model_config.id,
            bot_model_config_dict=bot_model_config_dict,
            bot_orchestration_config_entity=ModelConfigManager.convert_from_bot_model_config_dict(
                bot_model_config_dict=bot_model_config_dict
            ),
            conversation_id=conversation.id if conversation else None,
            regen_message_id=regen_message_id,
            inputs=conversation.inputs if conversation and not inputs else inputs,
            query=query.replace("\x00", "") if query else None,
            file_docs=file_docs,
            files=files,
            file_objs=file_objs,
            user_id=user_id,
            stream=stream,
            invoke_from=invoke_from,
        )

        # init generate records
        (conversation, message) = ChatService.init_generate_records(application_generate_entity)

        # init queue manager
        queue_manager = ApplicationQueueManager(
            task_id=application_generate_entity.task_id,
            user_id=application_generate_entity.user_id,
            conversation_id=conversation.id,
            app_mode=conversation.mode,
            message_id=message.id,
        )

        # new thread
        def run_worker_async():
            asyncio.run(
                ChatService.generate_worker(
                    application_generate_entity=application_generate_entity,
                    queue_manager=queue_manager,
                    conversation_id=conversation.id,
                    message_id=message.id,
                )
            )

        worker_thread = threading.Thread(target=run_worker_async)
        worker_thread.start()

        argo_tracking(
            ChatTrackingPayload(
                bot_category=application_generate_entity.bot_category,
                model_name=conversation.model_id,
                model_provider=conversation.model_provider,
                is_agent=bool(application_generate_entity.bot_orchestration_config_entity.agent),
                tools=conversation.tools,
            )
        )

        # return response or stream generator
        return ChatService.handle_response(
            application_generate_entity=application_generate_entity,
            queue_manager=queue_manager,
            conversation=conversation,
            message=message,
            stream=stream,
        )

    @staticmethod
    def get_cleaned_inputs(user_inputs: dict, bot_model_config: BotModelConfig):
        if user_inputs is None:
            user_inputs = {}

        filtered_inputs = {}

        input_form_config = bot_model_config.user_input_form_list
        for config in input_form_config:
            input_config = list(config.values())[0]
            variable = input_config["variable"]

            input_type = list(config.keys())[0]

            if variable not in user_inputs or not user_inputs[variable]:
                if input_config.get("required"):
                    raise ValueError(f"{variable} is required in input form")
                else:
                    filtered_inputs[variable] = input_config.get("default", "")
                    continue

            value = user_inputs[variable]

            if value:
                if not isinstance(value, str):
                    raise ValueError(f"{variable} in input form must be a string")

            if input_type == "select":
                options = input_config.get("options", [])
                if value not in options:
                    raise ValueError(f"{variable} in input form must be one of the following: {options}")
            else:
                if "max_length" in input_config:
                    max_length = input_config["max_length"]
                    if len(value) > max_length:
                        raise ValueError(f"{variable} in input form must be less than {max_length} characters")

            filtered_inputs[variable] = value.replace("\x00", "") if value else None

        return filtered_inputs

    @staticmethod
    async def generate_worker(
        application_generate_entity: ApplicationGenerateEntity,
        queue_manager: ApplicationQueueManager,
        conversation_id: str,
        message_id: str,
    ) -> None:
        bot_orchestration_config_entity = application_generate_entity.bot_orchestration_config_entity
        model_config = bot_orchestration_config_entity.bot_model_config
        if not model_config.model:
            await queue_manager.publish_error(
                translation_loader.translation.t("bot.bot_model_not_configured"),
                Errcode.ErrcodeBotModelNotConfigured,
                400,
                PublishFrom.APPLICATION_MANAGER,
            )
            return

        try:
            conversation = get_conversation(conversation_id)
            message = get_message(message_id)

            # runner: Union[AgentBotRunner, RoleplayApplicationRunner, BasicApplicationRunner]
            runner: Union[LanggraphAgentRunner, RoleplayApplicationRunner, BasicApplicationRunner]
            agent = application_generate_entity.bot_orchestration_config_entity.agent
            agent_strategy = agent.strategy if agent else None
            if agent_strategy and agent_strategy.value.startswith(PlanningStrategy.REACT_DEEP_RESEARCH.value):
                runner = LanggraphAgentRunner()
            elif bot_orchestration_config_entity.agent:
                runner = AgentBotRunner()
            elif application_generate_entity.bot_category == BotCategory.ROLEPLAY.value:
                runner = RoleplayApplicationRunner()
            else:
                runner = BasicApplicationRunner()

            await runner.run(
                application_generate_entity=application_generate_entity,
                queue_manager=queue_manager,
                conversation=conversation,
                message=message,
            )

        except ConversationTaskStoppedError:
            pass

        except ConnectError as e:
            if model_config.provider == OLLAMA_PROVIDER:
                await queue_manager.publish_error(
                    translation_loader.translation.t("ollama.ollama_connection_failed"),
                    Errcode.ErrcodeOllamaConnectionError,
                    500,
                    PublishFrom.APPLICATION_MANAGER,
                )
            else:
                await queue_manager.publish_error(
                    e,
                    Errcode.ErrcodeInternalServerError,
                    500,
                    pub_from=PublishFrom.APPLICATION_MANAGER,
                )

        except ollama.ResponseError as e:
            error_message = str(e)
            status_code = getattr(e, "status_code", None)
            if "model requires more system memory" in error_message:
                msg_key = "ollama.ollama_out_of_memory"
                err_code = Errcode.ErrcodeOllamaMemoryError
            elif status_code == 502:
                msg_key = "ollama.ollama_invoke_failed"
                err_code = Errcode.ErrcodeOllamaInvokeError
            elif status_code == 404:
                msg_key = "ollama.ollama_model_not_found"
                err_code = Errcode.ErrcodeOllamaModelNotFound
            else:
                await queue_manager.publish_error(
                    e,
                    Errcode.ErrcodeOllamaInvokeError,
                    500,
                    PublishFrom.APPLICATION_MANAGER,
                )
                return

            await queue_manager.publish_error(
                translation_loader.translation.t(msg_key),
                err_code,
                500,
                PublishFrom.APPLICATION_MANAGER,
            )
        except Exception as e:
            logging.exception("Unknown Error when generating")
            await queue_manager.publish_error(
                e,
                Errcode.ErrcodeInternalServerError,
                500,
                pub_from=PublishFrom.APPLICATION_MANAGER,
            )

    @staticmethod
    def init_generate_records(
        application_generate_entity: ApplicationGenerateEntity,
    ) -> tuple[Conversation, Message]:
        """
        Initialize generate records
        :param application_generate_entity: application generate entity
        :return:
        """
        bot_orchestration_config_entity = application_generate_entity.bot_orchestration_config_entity
        agent_dict = application_generate_entity.bot_model_config_dict.get("agent_mode", {})
        bot_record = get_bot(application_generate_entity.bot_id)

        bot_mode = bot_record.mode

        # get from source
        if application_generate_entity.invoke_from in [
            InvokeFrom.WEB_APP,
            InvokeFrom.SERVICE_API,
        ]:
            from_source = "api"
        else:
            from_source = "console"

        user_id = application_generate_entity.user_id
        file_docs = application_generate_entity.file_docs
        dataset_configs = (
            bot_orchestration_config_entity.dataset.configs if bot_orchestration_config_entity.dataset else {}
        )
        tools = agent_dict.get("tools", [])

        if not application_generate_entity.conversation_id:
            with db.session_scope() as session:
                conversation = Conversation(
                    bot_model_config_id=application_generate_entity.bot_model_config_id,
                    model_provider=bot_orchestration_config_entity.bot_model_config.provider,
                    model_id=bot_orchestration_config_entity.bot_model_config.model,
                    mode=bot_mode,
                    name="New conversation",
                    inputs=application_generate_entity.inputs,
                    docs=file_docs,
                    tools=tools,
                    datasets=dataset_configs,
                    system_instruction="",
                    system_instruction_tokens=0,
                    status="normal",
                    from_source=from_source,
                    from_user_id=user_id,
                    invoke_from=application_generate_entity.invoke_from.value,
                    agent_mode=agent_dict,
                )
                conversation.bot_id = bot_record.id

                session.add(conversation)
                session.commit()
                session.refresh(conversation)
        else:
            with db.session_scope() as session:
                conversation_or_none = (
                    session.query(Conversation)
                    .filter(
                        Conversation.id == application_generate_entity.conversation_id,
                    )
                    .first()
                )
                if conversation_or_none is None:
                    raise ValueError("Conversation not found")

                conversation = conversation_or_none

                conversation.bot_id = bot_record.id
                conversation.bot_model_config_id = application_generate_entity.bot_model_config_id
                conversation.model_provider = bot_orchestration_config_entity.bot_model_config.provider
                conversation.model_id = bot_orchestration_config_entity.bot_model_config.model
                conversation.datasets = dataset_configs
                conversation.tools = tools
                conversation.agent_mode = agent_dict
                conversation.inputs = application_generate_entity.inputs
                conversation.updated_at = datetime.now()

                if file_docs:
                    conversation.docs = list(set(conversation.docs + file_docs))
                session.commit()

        if not application_generate_entity.regen_message_id:
            with db.session_scope() as session:
                message = Message(
                    model_provider=bot_orchestration_config_entity.bot_model_config.provider,
                    model_id=bot_orchestration_config_entity.bot_model_config.model,
                    inputs=application_generate_entity.inputs,
                    query=application_generate_entity.query or "",
                    files=application_generate_entity.files,
                    message=[],
                    answer="",
                    provider_response_latency=0.0,
                    from_source=from_source,
                    from_user_id=user_id,
                    agent_based=bot_orchestration_config_entity.agent is not None,
                )
                message.bot_id = bot_record.id
                message.conversation_id = conversation.id

                session.add(message)
                session.commit()
                session.refresh(message)
        else:
            with db.session_scope() as session:
                message_or_none = (
                    session.query(Message)
                    .filter(
                        Message.id == application_generate_entity.regen_message_id,
                    )
                    .first()
                )
                if not message_or_none:
                    raise ValueError("Message not found")

                message = message_or_none

                # 删除关联的 MessageAgentThought
                session.query(MessageAgentThought).filter(MessageAgentThought.message_id == message.id).delete(
                    synchronize_session=False
                )

                # 清空 message 内容
                message.answer = ""
                message.message = []
                message.answer_tokens = 0
                message.message_tokens = 0
                message.provider_response_latency = 0.0
                message.status = "normal"
                message.error = ""
                message.message_metadata = ""
                message.is_stopped = False
                message.query = application_generate_entity.query or message.query

                session.commit()

        return conversation, message

    @staticmethod
    def handle_response(
        application_generate_entity: ApplicationGenerateEntity,
        queue_manager: ApplicationQueueManager,
        conversation: Conversation,
        message: Message,
        stream: bool = False,
    ) -> Union[dict, AsyncGenerator]:
        # init generate task pipeline
        generate_task_pipeline = GenerateTaskPipeline(
            application_generate_entity=application_generate_entity,
            queue_manager=queue_manager,
            conversation=conversation,
            message=message,
        )
        try:
            return generate_task_pipeline.process(stream=stream)

        except ValueError as e:
            raise e

    @staticmethod
    def stop_message(user_id: str, bot_id: str, task_id: str, message_id: str):
        if task_id == "":
            return
        bot = get_bot(bot_id)
        if not bot:
            raise ValueError("Bot not found")

        ApplicationQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, user_id)

        if message_id:
            with db.session_scope() as session:
                message = session.query(Message).filter_by(id=message_id).first()
                if not message:
                    raise ValueError(f"Message not found: {message_id}")

                message.is_stopped = True
                session.commit()


class ModelConfigManager:
    @staticmethod
    def convert_from_bot_model_config_dict(
        bot_model_config_dict: dict,
    ) -> BotOrchestrationConfigEntity:
        properties: dict[str, Any] = {}

        copy_bot_model_config_dict = bot_model_config_dict.copy()

        # model config
        model_config = ModelConfigManager.create_model_instance(copy_bot_model_config_dict["model"])
        model_config.network = copy_bot_model_config_dict.get("network", False)
        model_config.tool_config = copy_bot_model_config_dict.get("tool_config", [])
        model_config.prologue = copy_bot_model_config_dict.get("prologue", "")
        model_config.plugin_config = copy_bot_model_config_dict.get("plugin_config", {})
        properties["bot_model_config"] = model_config

        # prompt template
        prompt_type = PromptTemplateEntity.PromptType.value_of(copy_bot_model_config_dict["prompt_type"])
        simple_prompt_template = copy_bot_model_config_dict.get("pre_prompt", "")
        advanced_prompt_template = copy_bot_model_config_dict.get("advanced_prompt", "")
        properties["prompt_template"] = PromptTemplateEntity(
            prompt_type=prompt_type,
            simple_prompt_template=simple_prompt_template,
            advanced_prompt_template=advanced_prompt_template,
        )

        if copy_bot_model_config_dict.get("agent_mode"):
            agent_dict = copy_bot_model_config_dict.get("agent_mode", {})
            agent_strategy = agent_dict.get("strategy", "react")
            dataset_configs = {}
            for tool in agent_dict.get("tools", []):
                key = tool["type"]

                if key != "dataset":
                    continue

                if "enabled" not in tool or not tool["enabled"]:
                    continue

                dataset_id = tool["id"]
                doc_ids = tool["doc_ids"] if tool.get("doc_ids") else []
                dataset_configs[dataset_id] = doc_ids

            properties["dataset"] = DatasetEntity(
                configs=dataset_configs,
            )

            # tools = agent_dict.get('tools', [])
            # tools.append({"enabled": True, "type": "mcp_tool","name": "fetch", "id": uuid.uuid4().hex})
            # copy_bot_model_config_dict['agent_mode']['enabled'] = True
            # agent_dict['tools'] = tools

            if (
                "enabled" in copy_bot_model_config_dict["agent_mode"]
                and copy_bot_model_config_dict["agent_mode"]["enabled"]
            ):
                agent_tools = []
                for tool in agent_dict.get("tools", []):
                    agent_tool_properties = {"tool_id": tool["type"]}

                    tool_item = tool

                    if "enabled" not in tool_item or not tool_item["enabled"]:
                        continue

                    agent_tool_properties["config"] = tool_item
                    agent_tools.append(AgentToolEntity(**agent_tool_properties))

                properties["agent"] = AgentEntity(
                    provider=properties["bot_model_config"].provider,
                    model=properties["bot_model_config"].model,
                    strategy=PlanningStrategy(agent_strategy),
                    tools=agent_tools,
                    max_iteration=(copy_bot_model_config_dict["agent_mode"].get("max_iteration", 25)),
                )

        return BotOrchestrationConfigEntity(**properties)

    @staticmethod
    def create_model_instance(model_dict: dict) -> ModelConfigEntity:
        def extract_params(source: dict, keys: list) -> dict:
            return {key: source[key] for key in keys if key in source and source[key] is not None}

        # Extract completion parameters
        completion_params = model_dict.get("completion_params", {})
        param_keys = [
            "temperature",
            "top_p",
            "num_ctx",
            "num_predict",
            "repeat_last_n",
            "keep_alive",
            "format",
            "frequency_penalty",
            "presence_penalty",
        ]
        extracted_params = extract_params(completion_params, param_keys)
        extracted_params["model"] = model_dict.get("name")

        # Handle special parameters
        stop = completion_params.get("stop", [])
        provider = model_dict["provider"]

        # Initialize model instance based on provider
        llm_instance = model_provider_manager.get_model_instance(provider, model_params=extracted_params)

        # Get model mode and return the configuration entity
        model_mode = model_dict.get("mode")
        return ModelConfigEntity(
            provider=provider,
            model=model_dict.get("name"),
            mode=model_mode,
            llm_instance=llm_instance,
            parameters=extracted_params,
            stop=stop,
            plugin_config={},
            tool_config=[],
        )
