import logging
import platform
from threading import Thread

from configs.env import ARGO_STORAGE_PATH_DEPENDENCE_TOOL, IS_CHINA_NETWORK_ENV
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from services.tool import install_uv_npx

GITHUB_DEPENDENCIES_BASE_URL = "https://github.com/xark-argo/argo-dependency/releases/download/v0.0.1/"
GITEE_DEPENDENCIES_BASE_URL = "https://gitee.com/xark-argo/argo-dependency/releases/download/v0.0.1/"

BUN_PACKAGES = {
    "darwin-arm64": "bun-v1.2.8-darwin-aarch64.zip",
    "darwin-x64": "bun-v1.2.8-darwin-x64.zip",
    "win32-x64": "bun-v1.2.8-windows-x64.zip",
    "linux-x64": "bun-v1.2.8-linux-x64.zip",
    "linux-arm64": "bun-v1.2.8-linux-aarch64.zip",
}

UV_PACKAGES = {
    "darwin-arm64": "uv-0.6.12-aarch64-apple-darwin.tar.gz",
    "darwin-x64": "uv-0.6.12-x86_64-apple-darwin.tar.gz",
    "win32-x64": "uv-0.6.12-x86_64-pc-windows-msvc.zip",
    "win32-arm64": "uv-0.6.12-aarch64-pc-windows-msvc.zip",
    "win32-ia32": "uv-0.6.12-i686-pc-windows-msvc.zip",
    "linux-x64": "uv-0.6.12-x86_64-unknown-linux-gnu.tar.gz",
    "linux-arm64": "uv-0.6.12-aarch64-unknown-linux-gnu.tar.gz",
    "linux-ia32": "uv-0.6.12-i686-unknown-linux-gnu.tar.gz",
}

NODE_PACKAGES = {
    "darwin-arm64": "node_darwin_arm64.zip",
    "darwin-x64": "node_darwin_x86_64.zip",
    "win32-x64": "node_windows.zip",
    "linux-x64": "node_linux_x64.zip",
    "linux-arm64": "node_linux_arm64.zip",
}


def init():
    McpToolInstallService.mcp_tool_install("uv")
    McpToolInstallService.mcp_tool_install("bun")
    McpToolInstallService.mcp_tool_install("node")


def get_base_url(tool_name):
    return GITEE_DEPENDENCIES_BASE_URL if IS_CHINA_NETWORK_ENV else GITHUB_DEPENDENCIES_BASE_URL


def get_system_info():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine == "arm64":
            return "darwin-arm64"
        elif machine == "x86_64":
            return "darwin-x64"
    elif system == "windows":
        if machine == "arm64":
            return "win32-arm64"
        elif machine == "amd64":
            return "win32-x64"
    elif system == "linux":
        if machine == "aarch64":
            return "linux-arm64"
        elif machine == "x86_64":
            return "linux-x64"
    return system + "-" + machine


def get_package_name(tool_name):
    system_info = get_system_info()

    if tool_name == "uv":
        package = UV_PACKAGES.get(system_info)
    if tool_name == "bun":
        package = BUN_PACKAGES.get(system_info)
    if tool_name == "node":
        package = NODE_PACKAGES.get(system_info)

    return package


class McpToolInstallService:
    @staticmethod
    def mcp_tool_install(tool_name):
        base_url = get_base_url(tool_name)
        package = get_package_name(tool_name)
        if not package:
            ret = {
                "errcode": Errcode.ErrcodeInternalServerError.value,
                "message": translation_loader.translation.t("tool.mcp_tool_system_not_support")
                + tool_name
                + ": "
                + get_system_info(),
            }
            logging.error(ret["message"])
            return ret
        installer = install_uv_npx.McpToolInstaller(
            base_url=base_url,
            filename=package,
            bin_name=tool_name,
            target_dir=ARGO_STORAGE_PATH_DEPENDENCE_TOOL,
        )

        Thread(target=installer.process, daemon=True).start()
        return {"errcode": Errcode.ErrcodeSuccess.value, "message": "installing"}

    @staticmethod
    def mcp_tool_install_status(tool_name):
        base_url = get_base_url(tool_name)
        package = get_package_name(tool_name)
        if not package:
            return {
                "errcode": Errcode.ErrcodeInternalServerError.value,
                "message": translation_loader.translation.t("tool.mcp_tool_system_not_support")
                + tool_name
                + ": "
                + get_system_info(),
            }

        installer = install_uv_npx.McpToolInstaller(
            base_url=base_url,
            filename=package,
            bin_name=tool_name,
            target_dir=ARGO_STORAGE_PATH_DEPENDENCE_TOOL,
        )
        status = installer.is_exist()
        if status:
            return {"errcode": Errcode.ErrcodeSuccess.value, "message": "installed"}
        elif installer.is_processing():
            return {"errcode": Errcode.ErrcodeSuccess.value, "message": "installing"}
        return {"errcode": Errcode.ErrcodeSuccess.value, "message": "uninstalled"}
