from enum import Enum


class APIModelCategory(Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"
    VISION = "vision"
    TOOLS = "tools"
