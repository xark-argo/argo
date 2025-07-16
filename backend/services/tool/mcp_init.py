import json
import logging

from models.mcp_server import ConfigType, MCPStatus
from services.tool.mcp_server_service import McpServerService

MCP_PRESET = {
    "mcpServers": {
        "playwright": {
            "name": "Playwright Automation",
            "description": "提供浏览器自动化功能的模型上下文协议 (MCP) 服务器。此服务器使 LLM 能够"
            "通过结构化的可访问性快照与网页进行交互，而无需使用屏幕截图或视觉调整模型",
            "description_en": "A Model Context Protocol (MCP) server that provides browser "
            "automation capabilities using Playwright. This server enables "
            "LLMs to interact with web pages through structured accessibility "
            "snapshots, bypassing the need for screenshots or visually-tuned models.",
            "address": "https://github.com/microsoft/playwright-mcp",
            "command": "npx",
            "args": ["@playwright/mcp@latest"],
        },
        "fetch": {
            "name": "fetch",
            "description": "专为网页内容获取和转换而设计，允许大型语言模型（LLMs）通过将 HTML 转换为 Markdown 来"
            "检索和处理网页内容，以便更容易地消费。",
            "description_en": "Fetch is a Model Context Protocol (MCP) server "
            "designed for web content fetching and conversion, allowing Large Language Models (LLMs) "
            "to retrieve and process content from web pages by converting HTML into markdown for "
            "easier consumption.",
            "address": "https://github.com/smithery-ai/mcp-fetch",
            "command": "npx",
            "args": ["-y", "@kazuph/mcp-fetch"],
        },
        "edgeone-pages-mcp-server": {
            "name": "Pages Deploy",
            "description": "能够将 HTML 内容快速部署到 EdgeOne Pages 并生成公开访问链接。"
            "这使您能够立即预览和分享 AI 生成的网页内容。",
            "description_en": "Ability to quickly deploy HTML content to EdgeOne Pages and generate "
            "publicly accessible links. This allows you to instantly preview "
            "and share AI-generated web content.",
            "address": "https://edgeone.cloud.tencent.com/pages/document/173172415568367616",
            "command": "npx",
            "args": ["edgeone-pages-mcp"],
        },
        "tavily-mcp": {
            "name": "Tavily",
            "description": "AI 助手能够与 Tavily 的高级搜索和数据提取功能无缝集成。这种集成使 AI 模型"
            "能够实时访问网络信息，并配有复杂的过滤选项和特定领域的搜索功能。",
            "description_en": "The AI assistant can seamlessly integrate "
            "with Tavily’s advanced search and data extraction capabilities. This integration "
            "allows the AI model to access network information in real-time and is equipped "
            "with complex filtering options and specific domain search functions.",
            "address": "https://github.com/tavily-ai/tavily-mcp\nhttps://app.tavily.com/home",
            "command": "npx",
            "args": ["-y", "tavily-mcp@0.1.4"],
            "env": {"TAVILY_API_KEY": "your-api-key-here"},
        },
        "desktop-commander": {
            "name": "Desktop Commander",
            "description": "使用 AI 搜索、更新、管理本地文件和运行终端命令。",
            "description_en": "Use AI to search, update, manage local files and run terminal commands.",
            "address": "https://github.com/wonderwhy-er/DesktopCommanderMCP",
            "command": "npx",
            "args": ["-y", "@wonderwhy-er/desktop-commander"],
        },
    }
}


def init():
    server_list = McpServerService.get_server_list()
    for each_server in server_list:
        install_status = each_server["install_status"]
        server_id = each_server["id"]
        if install_status == MCPStatus.INSTALLING.value:
            McpServerService.update_tool_info(server_id=server_id, install_status=MCPStatus.FAIL.value)

    server_names = [each["name"] for each in server_list if each["preset"]]
    for _, params in MCP_PRESET["mcpServers"].items():
        if not isinstance(params, dict):
            continue
        server_name = params["name"]
        if server_name in server_names:
            continue
        description_zh, description_en = (
            f"{params['description']}\n\n地址：\n{params['address']}",
            f"{params['description_en']}\n\nAddress：\n{params['address']}",
        )
        server_params = {
            "name": server_name,
            "description": description_zh,
            "config_type": ConfigType.JSON.value,
            "json_command": json.dumps({server_name: params}),
        }

        valid, err, valid_param = McpServerService.check_valid(server_params)
        if not valid or not valid_param:
            logging.exception(f"Init mcp server[{server_name}] fail, error: {err}")
            continue

        try:
            server = McpServerService.create_mcp_server(
                name=valid_param.get("name", ""),
                description=valid_param.get("description", ""),
                description_en=description_en,
                command_type=valid_param.get("command_type", ""),
                command=valid_param.get("command", ""),
                env=valid_param.get("env", {}),
                url=valid_param.get("url", ""),
                preset=True,
            )
            logging.info(f"Init mcp server[{server_name} - {server.id}] ok.")
        except Exception as ex:
            logging.exception(f"Init mcp server[{server_name}] failed.")
