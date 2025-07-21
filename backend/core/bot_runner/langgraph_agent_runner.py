import asyncio
import json
import logging
import threading
from collections.abc import Iterator
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from core.agent.base_agent_runner import BaseAgentRunner
from core.agent.langgraph_agent.builder import build_graph_with_memory
from core.agent.langgraph_agent.prompts.planner_model import Plan
from core.agent.langgraph_agent.types import State as AgentState
from core.bot_runner.basic_bot_runner import BasicApplicationRunner
from core.callback_handler.agent_async_callback_handler import (
    AgentAsyncCallbackHandler,
)
from core.callback_handler.logging_out_async_callback_handler import (
    LoggingOutAsyncCallbackHandler,
)
from core.entities.application_entities import (
    ApplicationGenerateEntity,
    BotOrchestrationConfigEntity,
    InvokeFrom,
    ModelConfigEntity,
    PlanningStrategy,
)
from core.i18n.translation import translation_loader
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

# Create and run the Langgraph agent
# graph = self._build_agent_graph(
#     memory=memory,
#     agent_callback=agent_callback,
#     max_iterations=min(agent_entity.max_iteration, 15)
# )

# dict: thread_id -> graph
global_graph: dict[str, CompiledStateGraph] = {}


class LanggraphAgentRunner(BasicApplicationRunner):
    """Langgraph-based agent runner that replaces AgentBotRunner."""

    def __init__(self):
        self._mcp_cleanup = None

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

        # init instruction
        inputs = inputs or {}
        template = bot_orchestration_config.prompt_template
        instruction = template.advanced_prompt_template or template.simple_prompt_template or ""
        instruction = self._fill_in_inputs_from_external_data_tools(instruction, inputs)

        thread_id = conversation.id
        memory = None
        if application_generate_entity.conversation_id:
            memory = ConversationBufferDBMemory(
                return_messages=True,
                conversation_id=application_generate_entity.conversation_id,
                regen_message_id=application_generate_entity.regen_message_id,
                llm=bot_model_config.llm_instance,
            )

        messages: list[BaseMessage] = []
        if memory:
            messages.extend(memory.buffer)

        messages.append(user_message)
        # logging.info(f"LanggraphAgentRunner input messages: {messages}")

        # add agent callback to record agent thoughts
        agent_callback = AgentAsyncCallbackHandler(
            model_config=bot_model_config, message=message, queue_manager=queue_manager
        )

        # init tools
        tools = []
        max_iteration = 15
        agent_entity = bot_orchestration_config.agent

        # init initial state
        initial_state = AgentState(
            messages=messages,
            max_iterations=min(max_iteration, 15),
            auto_accepted_plan=False,
            instruction=instruction,
            research_topic=query,
        )
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,
            "callbacks": [agent_callback, LoggingOutAsyncCallbackHandler()],
            "thread_id": thread_id,
            "llm": bot_model_config.llm_instance,
            "tools": [],
            "locale": translation_loader.translation.language,
        }

        global global_graph
        graph = global_graph.get(thread_id)

        if agent_entity:
            max_iteration = agent_entity.max_iteration
            # update max_iterations from agent entity
            initial_state["max_iterations"] = min(max_iteration, 15)

            # Create base agent runner for tool management
            base_runner = BaseAgentRunner(
                model_config=bot_model_config,
                agent_config=agent_entity,
                queue_manager=queue_manager,
                instruction=instruction,
                message=message,
                memory=memory,
                user_id=application_generate_entity.user_id,
                callback_handler=agent_callback,
            )
            tools = await self._get_tools(base_runner, agent_entity.tools, application_generate_entity.invoke_from)

            # update config for langgraph agent
            config["tools"] = tools

            # choose graph
            tmp_graph = None
            agent_strategy = agent_entity.strategy if agent_entity else None
            if agent_strategy and agent_strategy == PlanningStrategy.REACT_DEEP_RESEARCH:
                tmp_graph = build_graph_with_memory("base")
            else:
                raise ValueError(f"Unsupported agent strategy: {agent_strategy}")
            if not graph:
                graph = tmp_graph

            # update initial state and graph
            edit_plan_str = f"[{translation_loader.translation.t('chat.edit_plan')}]".upper()
            accept_str = f"[{translation_loader.translation.t('chat.accepted')}]".upper()
            if (
                not initial_state["auto_accepted_plan"]
                and (query.upper().startswith(edit_plan_str) or query.upper().startswith(accept_str))
                and len(graph.get_state(config=config).interrupts) > 0
            ):
                initial_state = Command(resume=query)

                interrupt_count = len(graph.get_state(config=config).interrupts)
                logging.info(
                    f"resume with query: {query}, initial_state: {initial_state}, interrupt_count: {interrupt_count}"
                )
            else:
                # reconstruct graphs to clear state
                graph = tmp_graph
                # logging.info(f"new task, update graph: {graph.get_state(config=config)}")

            # logging.info(f"agent_run initial_state: {initial_state}")

        global_graph[thread_id] = graph

        # agent run
        async def agent_run(queue_mgr: ApplicationQueueManager, comiled_graph: CompiledStateGraph):
            error = None
            final_output = ""
            usage = self._get_usage_of_all_agent_thoughts(
                model_config=bot_orchestration_config.bot_model_config,
                message=message,
            )
            try:
                full_response = ""
                index = 0

                final_output = await self._astream_workflow_generator(
                    queue_mgr,
                    config,
                    comiled_graph,
                    initial_state,
                    thread_id,
                    application_generate_entity.conversation_id,
                    agent_callback,
                )
            finally:
                if self._mcp_cleanup:
                    await self._mcp_cleanup()

            await queue_mgr.publish_message_end(
                llm_result=LLMResult(
                    model=bot_orchestration_config.bot_model_config.model,
                    prompt_messages=[],
                    message=AIMessage(content=final_output),
                    usage=usage,
                ),
                pub_from=PublishFrom.APPLICATION_MANAGER,
            )
            agent_callback.done_set()

        def run_async_in_thread(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._handle_llm_result_stream(*args, **kwargs))
            loop.close()

        worker_thread = threading.Thread(
            target=run_async_in_thread,
            args=(queue_manager, bot_orchestration_config, agent_callback.iter(), message),
        )
        worker_thread.start()

        await agent_run(queue_manager, graph)

    async def _get_tools(self, base_runner: BaseAgentRunner, tool_configs, invoke_from: InvokeFrom) -> list[BaseTool]:
        """Get tools using the base agent runner."""
        tools = []

        # Get dataset tools
        dataset_tools = base_runner.create_dataset_retriever_tools(
            tool_configs=tool_configs,
            invoke_from=invoke_from,
        )
        if dataset_tools:
            tools.extend(dataset_tools)

        # Get MCP tools
        mcp_tools, cleanup = await base_runner.create_mcp_tools(
            tool_configs=tool_configs,
            invoke_from=invoke_from,
        )
        if mcp_tools:
            tools.extend(mcp_tools)
            # Store cleanup function for later use
            self._mcp_cleanup = cleanup
        else:
            self._mcp_cleanup = None

        return tools

    async def _astream_workflow_generator(
        self,
        queue_mgr: ApplicationQueueManager,
        config: dict,
        compiled_graph: CompiledStateGraph,
        initial_state: AgentState,
        thread_id="default_thread",
        conversation_id="",
        agent_callback: Optional[AgentAsyncCallbackHandler] = None,
    ):
        """Stream workflow execution with events."""
        # logger.info("=== GRAPH STREAMING EXECUTION START ===")
        # logger.info(f"Thread ID: {thread_id}, config: {config}, Initial state: {initial_state}")
        graph_messages = []
        try:
            # Use multiple stream modes to get comprehensive updates
            async for agent, _, event_data in compiled_graph.astream(
                initial_state, config=config, stream_mode=["messages", "values", "updates"], subgraphs=True
            ):
                if isinstance(event_data, dict):
                    if "__interrupt__" in event_data:
                        interrupt_event = {
                            "thread_id": thread_id,
                            "id": event_data["__interrupt__"][0].ns[0],
                            "role": "assistant",
                            "content": event_data["__interrupt__"][0].value,
                            "finish_reason": "interrupt",
                            "options": [
                                {"text": translation_loader.translation.t("chat.edit_plan"), "value": "edit_plan"},
                                {"text": translation_loader.translation.t("chat.accepted"), "value": "accepted"},
                            ],
                        }
                        logging.info(f"langgraph astream dict event: {event_data}, interrupt_event: {interrupt_event}")
                        await queue_mgr.publish_interrupt_message(
                            json.dumps(interrupt_event), PublishFrom.APPLICATION_MANAGER
                        )
                    else:
                        for k, v in event_data.items():
                            if isinstance(v, dict) and "current_plan" in v:
                                current_plan = v["current_plan"]
                                if isinstance(current_plan, Plan):
                                    current_plan_json = json.dumps(
                                        current_plan.dict_dump(), indent=4, ensure_ascii=False
                                    )
                                    await agent_callback.step_agent_loop(
                                        run_id="planner_" + agent_callback.message.id,
                                        meta={"langgraph_node": "planner"},
                                        message=AIMessage(content=current_plan_json),
                                    )

                        if isinstance(v, dict) and "messages" in v:
                            graph_messages = v["messages"]

        except Exception as e:
            err_info = str(e)
            logger.exception("Error In LanggraphAgent.")
            if "Recursion limit" in err_info:
                err_info = translation_loader.translation.t("chat.recursion_limit_error")
            raise ValueError(f"Error In LanggraphAgent: {err_info}")

        # logger.info("=== GRAPH STREAMING EXECUTION END ===")
        # return the last message content for the final output to save to history
        if len(graph_messages) > 0 and isinstance(graph_messages[-1], AIMessage):
            return graph_messages[-1].content
        else:
            return ""

    def _fill_in_inputs_from_external_data_tools(self, instruction: str, inputs: dict) -> str:
        """Fill in inputs from external data tools."""
        for key, value in inputs.items():
            try:
                instruction = instruction.replace(f"{{{{{key}}}}}", str(value))
            except Exception:
                continue
        return instruction

    def _get_usage_of_all_agent_thoughts(self, model_config: ModelConfigEntity, message: Message) -> LLMUsage:
        """Get usage of all agent thoughts."""
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
