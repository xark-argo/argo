from enum import Enum
from typing import Any

from pydantic import BaseModel

from core.queue.entities.llm_entities import LLMResult, LLMResultChunk


class QueueEvent(Enum):
    """
    QueueEvent enum
    """

    MESSAGE = "message"
    MESSAGE_REPLACE = "message-replace"
    MESSAGE_END = "message-end"
    RETRIEVER_RESOURCES = "retriever-resources"
    AGENT_THOUGHT = "agent-thought"
    INTERRUPT = "interrupt"
    PLAN = "plan"
    ERROR = "error"
    PING = "ping"
    STOP = "stop"


class AppQueueEvent(BaseModel):
    """
    QueueEvent entity
    """

    event: QueueEvent


class QueueMessageEvent(AppQueueEvent):
    """
    QueueMessageEvent entity
    """

    event: QueueEvent = QueueEvent.MESSAGE
    chunk: LLMResultChunk


class QueueMessageReplaceEvent(AppQueueEvent):
    """
    QueueMessageReplaceEvent entity
    """

    event: QueueEvent = QueueEvent.MESSAGE_REPLACE
    text: str


class QueueRetrieverResourcesEvent(AppQueueEvent):
    """
    QueueRetrieverResourcesEvent entity
    """

    event: QueueEvent = QueueEvent.RETRIEVER_RESOURCES
    retriever_resources: list[dict]


class QueueMessageEndEvent(AppQueueEvent):
    """
    QueueMessageEndEvent entity
    """

    event: QueueEvent = QueueEvent.MESSAGE_END
    llm_result: LLMResult


class QueueAgentThoughtEvent(AppQueueEvent):
    """
    QueueAgentThoughtEvent entity
    """

    event: QueueEvent = QueueEvent.AGENT_THOUGHT
    agent_thought_id: str


class InterruptEvent(AppQueueEvent):
    """
    InterruptMessageEvent entity
    """

    event: QueueEvent = QueueEvent.INTERRUPT
    interrupt_message: str


class PlanEvent(AppQueueEvent):
    """
    InterruptMessageEvent entity
    """

    event: QueueEvent = QueueEvent.PLAN
    plan_message: str


class QueueErrorEvent(AppQueueEvent):
    """
    QueueErrorEvent entity
    """

    event: QueueEvent = QueueEvent.ERROR
    error: Any
    code: int
    status: int


class QueuePingEvent(AppQueueEvent):
    """
    QueuePingEvent entity
    """

    event: QueueEvent = QueueEvent.PING


class QueueStopEvent(AppQueueEvent):
    """
    QueueStopEvent entity
    """

    class StopBy(Enum):
        """
        Stop by enum
        """

        USER_MANUAL = "user-manual"

    event: QueueEvent = QueueEvent.STOP
    stopped_by: StopBy


class QueueMessage(BaseModel):
    """
    QueueMessage entity
    """

    task_id: str
    message_id: str
    conversation_id: str
    app_mode: str
    event: AppQueueEvent
