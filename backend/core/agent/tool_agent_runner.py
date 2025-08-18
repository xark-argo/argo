import logging
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

# from core.agent.agent.tool_calling_agent import create_tool_calling_agent
from langgraph.prebuilt import create_react_agent

from core.agent.base_agent_runner import BaseAgentRunner
from core.callback_handler.logging_out_async_callback_handler import (
    LoggingOutAsyncCallbackHandler,
)
from core.entities.application_entities import InvokeFrom
from core.i18n.translation import translation_loader


class ToolCallAgentRunner(BaseAgentRunner):
    async def arun(self, user_message: HumanMessage, invoke_from: InvokeFrom, **kwargs: Any) -> str:
        """
        Run ToolCall agent application
        """

        tool_configs = self.agent_config.tools

        tools: list[BaseTool] = []

        dataset_tools = self.create_dataset_retriever_tools(
            tool_configs=tool_configs,
            invoke_from=invoke_from,
        )
        if dataset_tools:
            tools.extend(dataset_tools)

        mcp_tools = await self.create_mcp_tools(
            tool_configs=tool_configs,
            invoke_from=invoke_from,
        )
        if mcp_tools:
            tools.extend(mcp_tools)

        tool_names = [tool.name for tool in tools]
        logging.info(f"[ToolCallAgent] Tools in use: {tool_names}")

        max_iteration_steps = self.agent_config.max_iteration

        callbacks: list[BaseCallbackHandler] = [
            self.callback_handler,
            LoggingOutAsyncCallbackHandler(),
        ]

        messages: list[BaseMessage] = []
        if self.memory:
            messages.extend(self.memory.buffer)

        messages.append(user_message)

        try:
            agent = create_react_agent(
                model=self.model_config.llm_instance,
                tools=tools,
                prompt=self.instruction or "",
            )
        except NotImplementedError:
            msg = translation_loader.translation.t("chat.tool_call_not_supported")
            raise ValueError(msg)
        except Exception as e:
            raise e

        result = await agent.ainvoke(
            input={"messages": messages},
            config=RunnableConfig(callbacks=callbacks, recursion_limit=max_iteration_steps),
        )

        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, Sequence) and not isinstance(value, str):
                    last_item = value[-1]
                    if isinstance(last_item, AIMessage) and isinstance(last_item.content, str):
                        return last_item.content

        return ""
