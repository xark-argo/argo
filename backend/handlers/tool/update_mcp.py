import logging

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.tool.mcp_server_service import McpServerService


class UpdateMCPServerHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["id"]

    def post(self):
        """
        ---
        tags:
          - Tool
        summary: Update MCP Server
        description: Update MCP Server with the provided details
        parameters:
          - in: body
            name: body
            description: MCP Server details
            schema:
              type: object
              required:
                - id
              properties:
                id:
                  type: string
                name:
                  type: string
                description:
                  type: string
                command_type:
                  type: string
                command:
                  type: string
                env:
                  type: string
                url:
                  type: string
                enable:
                  type: bool
        responses:
          200:
            description: MCP Server update success
            schema:
              type: object
              properties:
                status:
                  type: bool
                msg:
                  type: string
          500:
            description: MCP Server update fail
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
        """
        id = self.req_dict.get("id", "")
        name = self.req_dict.get("name", "")
        description = self.req_dict.get("description", "")
        command_type = self.req_dict.get("command_type", None)
        command = self.req_dict.get("command", None)
        env = self.req_dict.get("env", "")
        url = self.req_dict.get("url", "")
        enable = self.req_dict.get("enable", None)

        headers = self.req_dict.get("headers", "")
        header_dict = McpServerService.parse_env(headers)

        language = translation_loader.translation.language
        env_info = McpServerService.parse_env(env)
        try:
            if language == "en":
                McpServerService.update_tool_info(
                    server_id=id,
                    name=name,
                    description_en=description,
                    command_type=command_type,
                    command=command,
                    env=env_info,
                    url=url,
                    enable=enable,
                    headers=header_dict,
                )
            else:
                McpServerService.update_tool_info(
                    server_id=id,
                    name=name,
                    description=description,
                    command_type=command_type,
                    command=command,
                    env=env_info,
                    url=url,
                    enable=enable,
                    headers=header_dict,
                )
            self.write(
                {
                    "status": True,
                    "msg": translation_loader.translation.t("tool.mcp_update_success"),
                }
            )

        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("tool.mcp_update_fail", ex=str(ex)),
                }
            )


api_router.add("/api/tool/update_mcp_server", UpdateMCPServerHandler)
