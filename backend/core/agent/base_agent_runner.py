import logging
from collections.abc import Awaitable
from typing import Any, Callable, Optional

from langchain_core.tools import BaseTool

from core.callback_handler.agent_async_callback_handler import (
    AgentAsyncCallbackHandler,
)
from core.entities.application_entities import (
    AgentEntity,
    AgentToolEntity,
    InvokeFrom,
    ModelConfigEntity,
)
from core.features.knowledge_tool import KnowledgeSearchTool
from core.memory.conversation_db_buffer_memory import (
    ConversationBufferDBMemory,
)
from core.queue.application_queue_manager import ApplicationQueueManager
from core.tools.mcp.client import MultiServerMCPClient
from core.tools.mcp.client_builder import create_server_parameter
from models.conversation import Message
from models.knowledge import get_collection_by_name
from models.mcp_server import get_server_info

CleanupFn = Callable[[], Awaitable[None]]


class BaseAgentRunner:
    def __init__(
        self,
        space_id: str,
        model_config: ModelConfigEntity,
        agent_config: AgentEntity,
        queue_manager: ApplicationQueueManager,
        message: Message,
        instruction: str,
        user_id: str,
        callback_handler: AgentAsyncCallbackHandler,
        memory: Optional[ConversationBufferDBMemory] = None,
    ) -> None:
        """
        Base class for running agents.
        """
        self.space_id = space_id
        self.model_config = model_config
        self.agent_config = agent_config
        self.queue_manager = queue_manager
        self.message = message
        self.user_id = user_id
        self.callback_handler = callback_handler
        self.memory = memory
        self.instruction = instruction

    def create_dataset_retriever_tools(
        self, tool_configs: list[AgentToolEntity], invoke_from: InvokeFrom
    ) -> list[BaseTool]:
        """
        Create dataset retriever tools from tool configs.
        """
        tools = []

        for tool_config in tool_configs:
            if tool_config.tool_id != "dataset":
                continue

            collection_name = tool_config.config.get("id")
            if not collection_name:
                continue

            knowledge = get_collection_by_name(collection_name)
            if not knowledge:
                continue

            partition_names = tool_config.config.get("doc_ids", [])
            tool = KnowledgeSearchTool.from_knowledge(
                collection_name,
                partition_names,
                hit_callbacks=[self.callback_handler],
            )

            if tool:
                tools.append(tool)

        return tools

    async def create_mcp_tools(
        self, tool_configs: list[AgentToolEntity], invoke_from: InvokeFrom
    ) -> tuple[list[BaseTool], CleanupFn]:
        """
        Create MCP tools by launching remote servers via their configs.
        """
        server_params: dict[str, dict] = {}
        server_name_id_map: dict[str, str] = {}

        for tool in tool_configs:
            if tool.tool_id != "mcp_tool":
                continue

            config_data = tool.config
            server_id = config_data.get("id")
            server_name = config_data.get("name")

            if not server_id or not server_name:
                continue

            server_config = get_server_info(server_id)
            if not server_config or not server_config.enable:
                logging.warning(f"Skipping MCP server '{server_name}' — not configured or disabled.")
                continue

            server_params[server_name] = create_server_parameter(server_config)
            server_name_id_map[server_name] = server_id

        if not server_params:

            async def noop_cleanup() -> None:
                pass

            return [], noop_cleanup

        client = await MultiServerMCPClient(server_params).__aenter__()  # noqa: PLC2801
        tools = client.get_tools()

        for item in tools:
            item.metadata["mcp_server_id"] = server_name_id_map.get(item.name, "")

        async def cleanup_fn():
            await client.__aexit__(None, None, None)

        return tools, cleanup_fn

    def get_mcp_config(self, server_id: str) -> dict[str, Any]:
        # return {
        #     "name": "fetch",
        #     "description": "专为网页内容获取和转换而设计，允许大型语言模型（LLMs）通过将 HTML 转换为 Markdown 来"
        #                    "检索和处理网页内容，以便更容易地消费。",
        #     "description_en": "Fetch is a Model Context Protocol (MCP) server "
        #                       "designed for web content fetching and conversion, \
        #                       allowing Large Language Models (LLMs) "
        #                       "to retrieve and process content from web pages by converting HTML into markdown for "
        #                       "easier consumption.",
        #     "address": "https://github.com/smithery-ai/mcp-fetch",
        #     "origin_command": "npx",
        #     "args": ["-y", "@kazuph/mcp-fetch"]
        # }
        # return {
        #       "url": "https://mcp.bochaai.com/sse",
        #       "headers": {
        #         "Authorization": "Bearer sk-67601577e6e84591933af7fcc8c1658e"
        #       }
        # }
        return {
            "name": "Sequential Thinking",
            "description": "通过结构化思维过程提供动态和反思性问题解决的工具",
            "description_en": "Provide tools for dynamic and "
            "reflective problem-solving through structured thinking processes",
            "address": "https://github.com/smithery-ai/reference-servers/tree/main/src/sequentialthinking",
            "origin_command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        }
