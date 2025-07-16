import os
import platform
from datetime import timedelta
from typing import Any

from configs.env import ARGO_STORAGE_PATH_DEPENDENCE_TOOL
from models import CommandType, MCPServer


def get_enhanced_path(original_path: str) -> str:
    path_separator = ";" if platform.system() == "Windows" else ":"

    existing_paths = set(filter(bool, original_path.split(path_separator)))

    home_dir = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""

    new_paths = []

    is_mac = platform.system() == "Darwin"
    is_linux = platform.system() == "Linux"
    is_win = platform.system() == "Windows"

    if is_mac:
        new_paths.extend(
            [
                "/bin",
                "/usr/bin",
                "/usr/local/bin",
                "/usr/local/sbin",
                "/opt/homebrew/bin",
                "/opt/homebrew/sbin",
                "/usr/local/opt/node/bin",
                os.path.join(home_dir, ".nvm/current/bin"),
                os.path.join(home_dir, ".npm-global/bin"),
                os.path.join(home_dir, ".yarn/bin"),
                os.path.join(home_dir, ".cargo/bin"),
                os.path.join(ARGO_STORAGE_PATH_DEPENDENCE_TOOL, "node/bin"),
                "/opt/local/bin",
            ]
        )

    if is_linux:
        new_paths.extend(
            [
                "/bin",
                "/usr/bin",
                "/usr/local/bin",
                os.path.join(home_dir, ".nvm/current/bin"),
                os.path.join(home_dir, ".npm-global/bin"),
                os.path.join(home_dir, ".yarn/bin"),
                os.path.join(home_dir, ".cargo/bin"),
                os.path.join(ARGO_STORAGE_PATH_DEPENDENCE_TOOL, "node/bin"),
                "/snap/bin",
            ]
        )

    if is_win:
        appdata = os.environ.get("APPDATA", "")
        new_paths.extend(
            [
                os.path.join(appdata, "npm"),
                os.path.join(home_dir, "AppData", "Local", "Yarn", "bin"),
                os.path.join(home_dir, ".cargo", "bin"),
                os.path.join(ARGO_STORAGE_PATH_DEPENDENCE_TOOL, "node"),
            ]
        )

    for path in new_paths:
        if path and path not in existing_paths:
            existing_paths.add(path)

    return path_separator.join(existing_paths)


def resolve_command_and_args(
    command: str, args: list[str], env: dict[str, Any]
) -> tuple[str, list[str], dict[str, Any]]:
    """
    Resolves actual command and modifies args accordingly.
    - If command is 'npx', may replace with 'bun' path
    - Adds '-y' and 'x' if needed
    - If command is 'uvx', resolves full path
    """
    if not command:
        return "", args or [], env or {}

    args = args.copy() if args else []
    env = env.copy() if env else {}

    env["PATH"] = get_enhanced_path(os.environ.get("PATH", ""))

    if command in ("npx", "bun", "bunx"):
        cmd = os.path.join(ARGO_STORAGE_PATH_DEPENDENCE_TOOL, "bun", "bun")
        if "-y" not in args:
            args.insert(0, "-y")
        if "x" not in args:
            args.insert(0, "x")
    elif command in ("uv", "uvx"):
        cmd = os.path.join(ARGO_STORAGE_PATH_DEPENDENCE_TOOL, "uv", command)
    else:
        cmd = command
    return cmd, args, env


def extract_command_args(command_type: str, command: str | None) -> tuple[str, list[str]]:
    if command_type == CommandType.STDIO.value and command:
        parts = [part.strip() for part in command.split()]
        if len(parts) >= 2:
            return parts[0], parts[1:]
        return command.strip(), []
    return "", []


def create_server_parameter(server_config: MCPServer) -> dict:
    """Create server parameter from the server configuration."""
    raw_command, raw_args = extract_command_args(server_config.command_type, server_config.command)
    read_timeout_seconds = 180

    if server_config.url:
        return {
            "url": server_config.url,
            "transport": "sse",
            "timeout": 5,
            "headers": server_config.headers,
            "sse_read_timeout": 180,
            "session_kwargs": {"read_timeout_seconds": timedelta(seconds=read_timeout_seconds)},
        }

    command, args, env = resolve_command_and_args(raw_command, raw_args, server_config.env)

    return {
        "command": command,
        "args": args,
        "env": env,
        "transport": "stdio",
        "session_kwargs": {"read_timeout_seconds": timedelta(seconds=read_timeout_seconds)},
    }
