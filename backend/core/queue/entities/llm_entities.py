from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel


class ModelUsage(BaseModel):
    pass


class LLMUsage(ModelUsage):
    """
    Model class for llm usage.
    """

    prompt_tokens: int
    completion_tokens: int

    @classmethod
    def empty_usage(cls):
        return cls(
            prompt_tokens=0,
            completion_tokens=0,
        )


class LLMResult(BaseModel):
    """
    Model class for llm result.
    """

    model: str
    prompt_messages: list[BaseMessage]
    message: AIMessage
    usage: Optional[LLMUsage] = None


class LLMResultChunkDelta(BaseModel):
    """
    Model class for llm result chunk delta.
    """

    index: int
    message: AIMessage
    metadata: Optional[dict[str, Any]] = None


class LLMResultChunk(BaseModel):
    """
    Model class for llm result chunk.
    """

    model: str
    prompt_messages: list[BaseMessage]
    delta: LLMResultChunkDelta
