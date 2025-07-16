import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.i18n.translation import translation_loader
from core.tools.mcp.client_builder import resolve_command_and_args
from database.db import session_scope
from events.mcp_server_event import mcp_server_enable_status
from models.mcp_server import CommandType, ConfigType, MCPServer, MCPStatus
from services.tool.sse import sse_client


class McpServerService:
    @staticmethod
    def create_mcp_server(
        name: str,
        description: str,
        command_type: str,
        command: str,
        env: dict,
        url: str,
        headers: dict = {},
        tools: list = [],
        description_en: str = "",
        enable=False,
        preset=False,
    ):
        with session_scope() as session:
            server = MCPServer(
                name=name,
                description=description,
                description_en=description_en,
                command_type=command_type,
                command=command,
                env=env,
                url=url,
                headers=headers,
                tools=tools,
                enable=enable,
                preset=preset,
            )
            session.add(server)
        return server

    @staticmethod
    def update_tool_info(
        server_id,
        name=None,
        description=None,
        description_en=None,
        command_type=None,
        command=None,
        env=None,
        url=None,
        install_status=None,
        headers=None,
        tools=None,
        enable=None,
    ):
        with session_scope() as session:
            if server := session.query(MCPServer).filter(MCPServer.id == server_id).one_or_none():
                if name is not None:
                    server.name = name
                if description is not None:
                    server.description = description
                if description_en is not None:
                    server.description_en = description_en
                if command_type is not None:
                    server.command_type = command_type
                if command is not None:
                    server.command = command
                if env is not None:
                    server.env = env
                if url is not None:
                    server.url = url
                if headers is not None:
                    server.headers = headers
                if tools is not None:
                    server.tools = tools
                if install_status is not None:
                    server.install_status = install_status
                if enable is not None:
                    server.enable = enable
                    mcp_server_enable_status.send(server.id, enable=enable, server_name=server.name)

    @staticmethod
    def get_server_list():
        result = []
        with session_scope() as session:
            query = session.query(MCPServer)
            server_list = query.all()
            for each_server in server_list:
                result.append(McpServerService.server_to_dict(each_server))
        return result

    @staticmethod
    def get_server_info(server_id):
        with session_scope() as session:
            if server := session.query(MCPServer).filter(MCPServer.id == server_id).one_or_none():
                return McpServerService.server_to_dict(server)
        return None

    @staticmethod
    def server_to_dict(server: MCPServer):
        env = server.env
        env_list = []
        if env is not None:
            for key, value in env.items():
                env_list.append(f"{key}={McpServerService.gen_value(value)}")
        env_info = "\n".join(env_list)

        header_info = ""
        if server.headers:
            header_list = [f"{key}: {McpServerService.gen_value(value)}" for key, value in server.headers.items()]
            header_info = "\n".join(header_list)

        origin_command, args = "", []
        if server.command_type == CommandType.STDIO.value:
            if server.command is not None:
                command_list = [each.strip() for each in server.command.split()]
                if len(command_list) >= 2:
                    origin_command, args = command_list[0], command_list[1:]

        if translation_loader.translation.language == "en":
            description = server.description_en
            if not description:
                description = server.description
        else:
            description = server.description
            if not description:
                description = server.description_en

        result = {
            "id": server.id,
            "name": server.name,
            "description": description,
            "command_type": server.command_type,
            "command": server.command,
            "env": env_info,
            "origin_command": origin_command,
            "origin_env": env,
            "args": args,
            "url": server.url,
            "headers": header_info,
            "origin_headers": server.headers,
            "tools": server.tools,
            "install_status": (MCPStatus.NOT_READY.value if server.install_status is None else server.install_status),
            "enable": server.enable,
            "preset": server.preset,
            "created_at": int(server.created_timestamp),
            "updated_at": int(server.updated_timestamp),
        }
        return result

    @staticmethod
    def parse_value(value):
        value = value.strip()
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value.strip('"').strip("'")

    @staticmethod
    def gen_value(value):
        if value is True:
            return "true"
        elif value is False:
            return "false"
        elif isinstance(value, str):
            try:
                value = int(value)
                return f'"{value}"'
            except ValueError:
                pass
            try:
                value = float(value)
                return f'"{value}"'
            except ValueError:
                pass
            return value
        else:
            return value

    @staticmethod
    def parse_env(env_text):
        env_dict = {}
        for line in env_text.strip().splitlines():
            line = line.strip()
            if not line or ("=" not in line and ":" not in line) or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
            else:
                key, value = line.split(":", 1)
            env_dict[key] = McpServerService.parse_value(value)
        return env_dict

    @staticmethod
    def check_valid(server_param: dict) -> tuple[bool, Optional[str], Optional[dict]]:
        try:
            valid_param = {}
            name = server_param.get("name", "")
            if not name:
                raise Exception(translation_loader.translation.t("tool.mcp_name_invalid"))
            valid_param["name"] = name

            description = server_param.get("description", "")
            description_en = server_param.get("description_en", "")
            if not description and not description_en:
                raise Exception(translation_loader.translation.t("tool.mcp_description_invalid"))
            valid_param["description"] = description
            valid_param["description_en"] = description_en

            config_type = server_param.get("config_type", "")
            if config_type == ConfigType.JSON.value:
                json_command = server_param.get("json_command", "")
                command_dict = json.loads(json_command)
                if "mcpServers" in command_dict:
                    command_dict = command_dict["mcpServers"]
                if len(list(command_dict.values())) != 1:
                    raise Exception(translation_loader.translation.t("tool.mcp_json_invalid"))
                command_dict = list(command_dict.values())[0]
                if not command_dict:
                    raise Exception(translation_loader.translation.t("tool.mcp_json_empty"))
                if not isinstance(command_dict, dict):
                    raise Exception(translation_loader.translation.t("tool.mcp_json_invalid"))
                if not (("command" in command_dict and "args" in command_dict) or ("url" in command_dict)):
                    raise Exception(translation_loader.translation.t("tool.mcp_json_invalid"))
                if "url" in command_dict:
                    valid_param["command_type"] = CommandType.SSE.value
                    valid_param["url"] = command_dict["url"]
                    header_dict = command_dict.get("headers", {})
                    valid_param["headers"] = header_dict
                else:
                    valid_param["command_type"] = CommandType.STDIO.value
                    origin_command, args = command_dict["command"], command_dict["args"]
                    if not (origin_command and args and isinstance(origin_command, str) and isinstance(args, list)):
                        raise Exception(translation_loader.translation.t("tool.mcp_json_invalid"))

                    command = f"{origin_command} {' '.join(args)}"
                    valid_param["command"] = command

                    if "env" in command_dict:
                        env_dict = command_dict["env"]
                        if not isinstance(env_dict, dict):
                            raise Exception(translation_loader.translation.t("tool.mcp_json_invalid"))
                        valid_param["env"] = env_dict
            elif config_type == ConfigType.COMMAND.value:
                command_type = server_param.get("command_type", "")
                if command_type == CommandType.STDIO.value:
                    command = server_param.get("command", "").strip()
                    if not command:
                        raise Exception(translation_loader.translation.t("tool.mcp_command_empty"))
                    command_list = command.split()
                    if len(command_list) < 2:
                        raise Exception(translation_loader.translation.t("tool.mcp_command_empty"))
                    valid_param["command"] = command
                    valid_param["command_type"] = CommandType.STDIO.value
                    env = server_param.get("env", "")
                    env_dict = McpServerService.parse_env(env)
                    valid_param["env"] = env_dict
                elif command_type == CommandType.SSE.value:
                    url = server_param.get("url", "")
                    if not url:
                        raise Exception(translation_loader.translation.t("tool.mcp_sse_url_empty"))
                    headers = server_param.get("headers", "")
                    header_dict = McpServerService.parse_env(headers)
                    valid_param["url"] = url
                    valid_param["headers"] = header_dict
                    valid_param["command_type"] = CommandType.SSE.value
                else:
                    raise Exception(translation_loader.translation.t("tool.mcp_command_type_empty"))
            else:
                raise Exception(translation_loader.translation.t("tool.unknown_mcp_config_type"))
            return True, None, valid_param
        except Exception as ex:
            logging.exception("Check MCP server param failed.")
            return False, str(ex), None

    @staticmethod
    def delete_server(server_id) -> bool:
        with session_scope() as session:
            if server := session.query(MCPServer).filter(MCPServer.id == server_id).one_or_none():
                session.delete(server)
                return True
        return False

    @staticmethod
    def create_server_parameter(server: MCPServer) -> dict:
        if server.command_type == CommandType.STDIO.value and server.command:
            command_list = [each.strip() for each in server.command.split()]
            origin_command, args = command_list[0], command_list[1:]
            command, args, env = resolve_command_and_args(origin_command, args, server.env)
            return {
                "command": command,
                "args": args,
                "env": env,
                "transport": "stdio",
                "encoding_error_handler": "strict",
            }
        else:
            return {
                "url": server.url,
                "headers": server.headers,
                "timeout": 5,
                "sse_read_timeout": 10,
            }

    @staticmethod
    async def check_server(server_id) -> tuple[Optional[dict], Optional[str]]:
        with session_scope() as session:
            server = session.query(MCPServer).filter(MCPServer.id == server_id).one_or_none()
        if server is None:
            return None, translation_loader.translation.t("tool.mcp_server_not_found")

        try:
            McpServerService.update_tool_info(server_id=server_id, install_status=MCPStatus.INSTALLING.value)
            server_config = McpServerService.create_server_parameter(server)
            tool_list = []

            async with AsyncExitStack() as exit_stack:
                if server.command_type == CommandType.STDIO.value:
                    stdio_transport = await exit_stack.enter_async_context(
                        stdio_client(StdioServerParameters(**server_config))
                    )
                    read, write = stdio_transport
                else:
                    sse_transport = await exit_stack.enter_async_context(sse_client(**server_config))
                    read, write = sse_transport
                mcp_session: ClientSession = await exit_stack.enter_async_context(ClientSession(read, write))

                try:
                    await asyncio.wait_for(mcp_session.initialize(), timeout=5 * 60)
                except asyncio.TimeoutError as ex:
                    logging.exception("Timeout while initializing MCP server.")
                    McpServerService.update_tool_info(server_id=server.id, install_status=MCPStatus.FAIL.value)
                    return None, translation_loader.translation.t("tool.mcp_server_initialize_fail")

                response = await mcp_session.list_tools()
                tools = response.tools
                count = 0
                for tool in tools:
                    if "properties" in tool.inputSchema:
                        count += 1
                        tool_info = {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema,
                        }
                        tool_list.append(tool_info)
            if count == 0:
                McpServerService.update_tool_info(
                    server_id=server.id,
                    tools=tool_list,
                    install_status=MCPStatus.FAIL.value,
                )
            else:
                McpServerService.update_tool_info(
                    server_id=server.id,
                    tools=tool_list,
                    enable=True,
                    install_status=MCPStatus.SUCCESS.value,
                )
            server_info = McpServerService.get_server_info(server_id=server.id)
            return server_info, None
        except Exception as ex:
            logging.exception("Unexpected error while checking MCP server.")
            McpServerService.update_tool_info(server_id=server.id, install_status=MCPStatus.FAIL.value)
            return None, translation_loader.translation.t("tool.mcp_server_initialize_fail")
