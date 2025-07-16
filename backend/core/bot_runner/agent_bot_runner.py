import asyncio
import logging
import threading
from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AIMessage

from core.agent.tool_agent_runner import ToolCallAgentRunner
from core.bot_runner.basic_bot_runner import BasicApplicationRunner
from core.callback_handler.agent_async_callback_handler import (
    AgentAsyncCallbackHandler,
)
from core.entities.application_entities import (
    ApplicationGenerateEntity,
    BotOrchestrationConfigEntity,
    ModelConfigEntity,
)
from core.memory.conversation_db_buffer_memory import (
    ConversationBufferDBMemory,
)
from core.queue.application_queue_manager import (
    ApplicationQueueManager,
    PublishFrom,
)
from core.queue.entities.llm_entities import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
)
from models.bot import get_bot
from models.conversation import Conversation, Message, get_agent_thoughts

logger = logging.getLogger(__name__)


class AgentBotRunner(BasicApplicationRunner):
    async def run(
        self,
        application_generate_entity: ApplicationGenerateEntity,
        queue_manager: ApplicationQueueManager,
        conversation: Conversation,
        message: Message,
    ) -> None:
        bot_record = get_bot(application_generate_entity.bot_id)
        if not bot_record:
            raise ValueError("Bot not found")

        bot_orchestration_config = application_generate_entity.bot_orchestration_config_entity
        bot_model_config = bot_orchestration_config.bot_model_config

        query = application_generate_entity.query
        inputs = application_generate_entity.inputs

        user_message = self.get_last_user_message(query, application_generate_entity.file_objs)

        agent_entity = bot_orchestration_config.agent
        assert agent_entity is not None

        # init instruction
        inputs = inputs or {}
        template = bot_orchestration_config.prompt_template
        instruction = template.advanced_prompt_template or template.simple_prompt_template or ""
        instruction = self._fill_in_inputs_from_external_data_tools(instruction, inputs)

        memory = None
        if application_generate_entity.conversation_id:
            memory = ConversationBufferDBMemory(
                return_messages=True,
                conversation_id=application_generate_entity.conversation_id,
                regen_message_id=application_generate_entity.regen_message_id,
                llm=bot_model_config.llm_instance,
            )

        # add agent callback to record agent thoughts
        agent_callback = AgentAsyncCallbackHandler(
            model_config=bot_model_config, message=message, queue_manager=queue_manager
        )

        agent_runner = ToolCallAgentRunner(
            space_id=application_generate_entity.space_id,
            model_config=bot_model_config,
            agent_config=agent_entity,
            queue_manager=queue_manager,
            instruction=instruction,
            message=message,
            memory=memory,
            user_id=application_generate_entity.user_id,
            callback_handler=agent_callback,
        )

        # agent run
        async def agent_run(*args, **kwargs):
            error = None
            try:
                output = await agent_runner.arun(*args, **kwargs)
                usage = self._get_usage_of_all_agent_thoughts(
                    model_config=bot_orchestration_config.bot_model_config,
                    message=message,
                )
                await queue_manager.publish_message_end(
                    llm_result=LLMResult(
                        model=bot_orchestration_config.bot_model_config.model,
                        prompt_messages=[],
                        message=AIMessage(content=output),
                        usage=usage,
                    ),
                    pub_from=PublishFrom.APPLICATION_MANAGER,
                )
            except Exception as e:
                error = e
            agent_callback.done_set(error)

        def run_async_in_thread(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(agent_run(*args, **kwargs))
            loop.close()

        worker_thread = threading.Thread(
            target=run_async_in_thread,
            args=(user_message, application_generate_entity.invoke_from),
        )
        worker_thread.start()

        await self._handle_llm_result_stream(
            queue_manager=queue_manager,
            bot_orchestration_config=bot_orchestration_config,
            llm_iter=agent_callback.iter(),
            message=message,
        )

    def _fill_in_inputs_from_external_data_tools(self, instruction: str, inputs: dict) -> str:
        """
        fill in inputs from external data tools
        """
        for key, value in inputs.items():
            try:
                instruction = instruction.replace(f"{{{{{key}}}}}", str(value))
            except Exception as e:
                continue

        return instruction

    def _get_usage_of_all_agent_thoughts(self, model_config: ModelConfigEntity, message: Message) -> LLMUsage:
        """
        Get usage of all agent thoughts
        :param model_config: model config
        :param message: message
        :return:
        """
        agent_thoughts = get_agent_thoughts(message.id)

        all_message_tokens = 0
        all_answer_tokens = 0
        for agent_thought in agent_thoughts:
            if agent_thought.message_token and agent_thought.answer_token:
                all_message_tokens += agent_thought.message_token
                all_answer_tokens += agent_thought.answer_token

        return LLMUsage(
            prompt_tokens=all_message_tokens,
            completion_tokens=all_answer_tokens,
        )

    async def _handle_llm_result_stream(
        self,
        queue_manager: ApplicationQueueManager,
        bot_orchestration_config: BotOrchestrationConfigEntity,
        llm_iter: Iterator[Any],
        message: Message,
    ) -> None:
        index = 0
        for result in llm_iter:
            if not isinstance(result, tuple):
                continue

            meta, token = result

            await queue_manager.publish_chunk_message(
                LLMResultChunk(
                    model=bot_orchestration_config.bot_model_config.model,
                    prompt_messages=[],
                    delta=LLMResultChunkDelta(index=index, message=AIMessage(content=token), metadata=meta),
                ),
                PublishFrom.APPLICATION_MANAGER,
            )
            index += 1
