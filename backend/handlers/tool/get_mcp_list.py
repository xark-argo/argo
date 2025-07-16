from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.tool.mcp_server_service import McpServerService


class GetMCPListHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = []

    def get(self):
        """
        ---
        tags:
          - Tool
        summary: Get all MCP Server
        description: Get all MCP Server
        parameters: []
        responses:
          200:
            description: A list of MCP Server
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                server_list:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: string
                      name:
                        type: string
                      description:
                        type: string
                      config_type:
                        type: string
                      json_command:
                        type: string
                      command_type:
                        type: string
                      command:
                        type: string
                      env:
                        type: string
                      url:
                        type: string
          400:
            description: Invalid input
          401:
            description: Process error
        """
        server_list = McpServerService.get_server_list()
        self.write({"server_list": server_list})


api_router.add("/api/tool/get_mcp_list", GetMCPListHandler)
