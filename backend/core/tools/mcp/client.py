import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient as LCMultiServerMCPClient
from mcp import ClientSession
from mcp.shared.exceptions import McpError

from core.i18n.translation import translation_loader
from core.tools.mcp.tools import load_mcp_tools


class MultiServerMCPClient(LCMultiServerMCPClient):
    """Client for connecting to multiple MCP servers and loading LangChain-compatible tools from them."""

    # This method is used by LCMultiServerMCPClient via dynamic dispatch.
    # vulture: ignore
    async def _initialize_session_and_load_tools(self, server_name: str, session: ClientSession) -> None:
        """Initialize a session and load tools from it.

        Args:
            server_name: Name to identify this server connection
            session: The ClientSession to initialize
        """
        # Initialize the session
        await session.initialize()
        self.sessions[server_name] = session

        # Load tools from this server
        server_tools = await load_mcp_tools(session)
        self.server_name_to_tools[server_name] = server_tools

    async def __aenter__(self) -> "MultiServerMCPClient":
        def format_error(name: str, detail: str) -> str:
            prefix = translation_loader.translation.t("tool.mcp_server_connection_failed_prefix", name=name)
            return f"{prefix}: {detail}"

        try:
            connections = self.connections or {}
            for server_name, connection in connections.items():
                try:
                    await self.connect_to_server(server_name, **connection)
                except McpError as e:
                    if e.error.code == httpx.codes.REQUEST_TIMEOUT:
                        msg = translation_loader.translation.t("tool.mcp_server_request_timeout", name=server_name)
                        raise RuntimeError(format_error(server_name, msg)) from e

                    raise RuntimeError(format_error(server_name, str(e))) from e

                except Exception as e:
                    raise RuntimeError(format_error(server_name, str(e))) from e

            return self
        except Exception as e:
            try:
                await self.exit_stack.aclose()
            except Exception:
                pass

            raise e
