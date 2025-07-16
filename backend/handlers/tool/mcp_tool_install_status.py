from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.tool.mcp_tool_install import McpToolInstallService


class McpToolInstallStatusHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)

    def get(self):
        """
        ---
        tags:
          - Tool
        summary: "Mcp tool install status: bun,uv
        description: get mcp tool install status(bun,uv)"
        responses:
          200:
            description: "Mcp tool install status: installed, uninstalled, installing"
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
        """

        bun_result = McpToolInstallService.mcp_tool_install_status("bun")
        uv_result = McpToolInstallService.mcp_tool_install_status("uv")
        node_result = McpToolInstallService.mcp_tool_install_status("node")

        # example: errcode -1:success other:error
        # {"bun": {"errcode": -2, "message": "error reason"},
        #  "uv": {"errcode": -1, "message": "installing"}}
        self.write({"bun": bun_result, "node": node_result, "uv": uv_result})


api_router.add("/api/tool/mcp_tool_install_status", McpToolInstallStatusHandler)
