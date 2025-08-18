from core.errors.errcode import Errcode
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.tool.mcp_server_service import McpServerService


class CheckMCPServerHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["id"]

    async def post(self):
        """
        ---
        tags:
          - Tool
        summary: Check MCP Server
        description: Check MCP Server by server id
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
            description: MCP Server check ok
            schema:
              type: object
              properties:
                server_info:
                  type: object
          500:
            description: MCP Server check fail
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
        """
        server_id = self.req_dict.get("id", "")
        server_info, msg = await McpServerService.validate_mcp_server(server_id)
        if server_info:
            self.write({"server_info": server_info})
        else:
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": msg})


api_router.add("/api/tool/check_mcp_server", CheckMCPServerHandler)
