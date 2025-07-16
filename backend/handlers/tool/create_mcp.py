import logging

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.mcp_server import ConfigType
from services.tool.mcp_server_service import McpServerService


class CreateMCPServerHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["name", "description", "config_type"]

    def post(self):
        """
        ---
        tags:
          - Tool
        summary: Create MCP Server
        description: Create MCP Server with the provided details
        parameters:
          - in: body
            name: body
            description: MCP Server details
            schema:
              type: object
              required:
                - name
                - description
                - config_type
              properties:
                name:
                  type: string
                description:
                  type: string
                config_type:
                  type: string
                command_type:
                  type: string
                json_command:
                  type: string
                command:
                  type: string
                env:
                  type: string
                url:
                  type: string
                headers:
                  type: string
        responses:
          200:
            description: MCP Server created successfully
            schema:
              type: object
              properties:
                status:
                  type: bool
                id:
                  type: string
          500:
            description: MCP Server created fail
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
        """
        name = self.req_dict.get("name", "")
        description = self.req_dict.get("description", "")
        config_type = self.req_dict.get("config_type", ConfigType.JSON.value)
        command_type = self.req_dict.get("command_type", "")
        json_command = self.req_dict.get("json_command", "{}")
        headers = self.req_dict.get("headers", "{}")
        command = self.req_dict.get("command", "")
        env = self.req_dict.get("env", "")
        url = self.req_dict.get("url", "")

        language = translation_loader.translation.language
        description_en = ""
        if language == "en":
            description_en = description

        server_params = {
            "name": name,
            "description": description,
            "description_en": description_en,
            "config_type": config_type,
            "command_type": command_type,
            "json_command": json_command,
            "headers": headers,
            "command": command,
            "env": env,
            "url": url,
        }

        valid, err, valid_param = McpServerService.check_valid(server_params)
        if not valid or not valid_param:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInvalidRequest.value,
                    "msg": translation_loader.translation.t("tool.add_mcp_fail", ex=err),
                }
            )
            return

        try:
            server = McpServerService.create_mcp_server(
                name=valid_param.get("name", ""),
                description=valid_param.get("description", ""),
                description_en=valid_param.get("description_en", ""),
                command_type=valid_param.get("command_type", ""),
                command=valid_param.get("command", ""),
                env=valid_param.get("env", {}),
                url=valid_param.get("url", ""),
                headers=valid_param.get("headers", {}),
            )
            self.write(
                {
                    "status": True,
                    "id": server.id,
                    "msg": translation_loader.translation.t("tool.add_mcp_success"),
                }
            )
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("tool.add_mcp_fail", ex=str(ex)),
                }
            )


api_router.add("/api/tool/create_mcp_server", CreateMCPServerHandler)
