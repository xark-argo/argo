from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.tool.mcp_server_service import McpServerService


class DeleteMCPServerHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["id"]

    def post(self):
        """
        ---
        tags:
          - Tool
        summary: Delete MCP Server
        description: Delete MCP Server with the provided server id
        parameters:
          - in: body
            name: body
            description: MCP Server id
            schema:
              type: object
              required:
                - id
              properties:
                id:
                  type: string
        responses:
          200:
            description: MCP Server delete successfully
            schema:
              type: object
              properties:
                status:
                  type: bool
                msg:
                  type: string
          500:
            description: MCP Server delete fail
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
        """
        server_id = self.req_dict.get("id", "")
        is_delete = McpServerService.delete_server(server_id=server_id)
        if is_delete:
            self.write(
                {
                    "status": True,
                    "msg": translation_loader.translation.t("tool.mcp_delete_success"),
                }
            )
        else:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("tool.mcp_delete_fail"),
                }
            )


api_router.add("/api/tool/delete_mcp_server", DeleteMCPServerHandler)
