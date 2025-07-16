from typing import Any

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from mcp import ClientSession
from mcp.types import CallToolResult, EmbeddedResource, ImageContent, TextContent
from mcp.types import Tool as MCPTool
from pydantic import ValidationError

NonTextContent = ImageContent | EmbeddedResource


def _handle_validation_error(e: ValidationError) -> str:
    return str(e)


def _normalize_schema_types(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema

    new_schema = {}

    for key, value in schema.items():
        if key == "type" and isinstance(value, list):
            new_schema["anyOf"] = [{"type": v} for v in value]
            continue

        if isinstance(value, dict):
            new_schema[key] = _normalize_schema_types(value)
        elif isinstance(value, list):
            new_schema[key] = [_normalize_schema_types(item) if isinstance(item, dict) else item for item in value]
        else:
            new_schema[key] = value

    return new_schema


def _convert_call_tool_result(
    call_tool_result: CallToolResult,
) -> tuple[str | list[str], list[NonTextContent] | None]:
    text_contents: list[TextContent] = []
    non_text_contents = []
    for content in call_tool_result.content:
        if isinstance(content, TextContent):
            text_contents.append(content)
        else:
            non_text_contents.append(content)

    tool_content: str | list[str] = [content.text for content in text_contents]
    if len(text_contents) == 1:
        tool_content = tool_content[0]

    if call_tool_result.isError:
        raise ToolException(tool_content)

    return tool_content, non_text_contents or None


def convert_mcp_tool_to_langchain_tool(
    session: ClientSession,
    tool: MCPTool,
) -> BaseTool:
    """Convert an MCP tool to a LangChain tool.

    NOTE: this tool can be executed only in a context of an active MCP client session.

    Args:
        session: MCP client session
        tool: MCP tool to convert

    Returns:
        a LangChain tool
    """

    async def call_tool(
        **arguments: dict[str, Any],
    ) -> tuple[str | list[str], list[NonTextContent] | None]:
        try:
            call_tool_result = await session.call_tool(tool.name, arguments)
            return _convert_call_tool_result(call_tool_result)
        except Exception as e:
            raise ToolException(str(e))

    return StructuredTool(
        name=tool.name,
        description=tool.description or "",
        args_schema=_normalize_schema_types(tool.inputSchema),
        coroutine=call_tool,
        handle_tool_error=True,
        handle_validation_error=_handle_validation_error,
        response_format="content_and_artifact",
        metadata={"tool_type": "mcp_tool", "mcp_server_name": tool.name},
    )


async def load_mcp_tools(session: ClientSession) -> list[BaseTool]:
    """Load all available MCP tools and convert them to LangChain tools."""
    tools = await session.list_tools()
    return [convert_mcp_tool_to_langchain_tool(session, tool) for tool in tools.tools]
