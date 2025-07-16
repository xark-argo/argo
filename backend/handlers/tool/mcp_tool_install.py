from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.tool.mcp_tool_install import McpToolInstallService


class McpToolInstallHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)

    def get(self):
        """
        ---
        tags:
          - Tool
        summary: "Install Mcp tool: bun,uv"
        description: download and install mcp tool(bun,uv) to .argo dir
        responses:
          200:
            description: Mcp tool install triggered successfully
            schema:
              type: object
              properties:
                bun:
                  type: object
                  properties:
                    errcode:
                      type: string
                    message:
                      type: string
                uv:
                  type: object
                  properties:
                    errcode:
                      type: string
                    message:
                      type: string
          400:
            description: Invalid input
          401:
            description: Process error
        """

        bun_result = McpToolInstallService.mcp_tool_install("bun")
        uv_result = McpToolInstallService.mcp_tool_install("uv")
        node_result = McpToolInstallService.mcp_tool_install("node")

        # example: errcode -1:success other:error
        # {"bun": {"errcode": -2, "message": "error reason"},
        #  "uv": {"errcode": -1, "message": "installing"}}
        self.write({"bun": bun_result, "node": node_result, "uv": uv_result})


api_router.add("/api/tool/mcp_tool_install", McpToolInstallHandler)
