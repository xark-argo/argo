import asyncio
from collections.abc import AsyncGenerator
from enum import Enum
from typing import Any

from sqlalchemy.orm import DeclarativeMeta

from core.entities.application_entities import InvokeFrom
from core.errors.errcode import Errcode
from core.queue.entities.queue_entities import (
    AppQueueEvent,
    InterruptEvent,
    LLMResult,
    LLMResultChunk,
    PlanEvent,
    QueueAgentThoughtEvent,
    QueueErrorEvent,
    QueueMessage,
    QueueMessageEndEvent,
    QueueMessageEvent,
    QueuePingEvent,
    QueueStopEvent,
)
from database.cache import local_cache


class PublishFrom(Enum):
    APPLICATION_MANAGER = 1
    TASK_PIPELINE = 2


class ApplicationQueueManager:
    def __init__(
        self,
        task_id: str,
        user_id: str,
        conversation_id: str,
        app_mode: str,
        message_id: str,
    ) -> None:
        if not user_id:
            raise ValueError("user is required")

        self._task_id = task_id
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._app_mode = app_mode
        self._message_id = message_id

        user_prefix = "user"
        local_cache.setdefault(
            ApplicationQueueManager._generate_task_belong_cache_key(self._task_id),
            f"{user_prefix}-{self._user_id}",
        )

        q: asyncio.Queue[QueueMessage | None] = asyncio.Queue()

        self._q = q

    async def listen(self) -> AsyncGenerator:
        """
        Listen to queue
        :return:
        """
        # wait for 10 minutes to stop listen
        listen_timeout = 6000
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        last_ping_time: int = 0

        await self.publish(QueuePingEvent(), PublishFrom.TASK_PIPELINE)

        while True:
            try:
                message = await asyncio.wait_for(self._q.get(), timeout=0.05)
                if message is None:
                    break
                yield message
            except asyncio.TimeoutError:
                await asyncio.sleep(0)
            finally:
                elapsed_time = loop.time() - start_time
                if elapsed_time >= listen_timeout or self._is_stopped():
                    # publish two messages to make sure the client can receive the stop signal
                    # and stop listening after the stop signal processed
                    await self.publish(
                        QueueStopEvent(stopped_by=QueueStopEvent.StopBy.USER_MANUAL),
                        PublishFrom.TASK_PIPELINE,
                    )

                if elapsed_time // 10 > last_ping_time:
                    await self.publish(QueuePingEvent(), PublishFrom.TASK_PIPELINE)
                    last_ping_time = int(elapsed_time // 10)

    async def stop_listen(self) -> None:
        """
        Stop listen to queue
        :return:
        """
        await self._q.put(None)

    async def publish_agent_thought(self, agent_thought_id: str, pub_from: PublishFrom) -> None:
        """
        Publish agent thought
        :param agent_thought_id: message agent thought id
        :param pub_from: publish from
        :return:
        """
        await self.publish(QueueAgentThoughtEvent(agent_thought_id=agent_thought_id), pub_from)

    async def publish_interrupt_message(self, interrupt_message: str, pub_from: PublishFrom) -> None:
        """
        Publish interrupt message
        :param interrupt_message: {"thread_id": "xxx", "id": "human_feedback",
            "role": "assistant", "content": "Please Review the Plan.",
            "finish_reason": "interrupt", "options": [{"text": "Edit plan", "value": "edit_plan"},
            {"text": "Start research", "value": "accepted"}]}
        :param pub_from: publish from
        :return:
        """
        await self.publish(InterruptEvent(interrupt_message=interrupt_message), pub_from)

    async def publish_plan_message(self, plan_message: str, pub_from: PublishFrom) -> None:
        """
        Publish plan message
        :param plan_message: Plan message
        :param pub_from: publish from
        :return:
        """
        await self.publish(PlanEvent(plan_message=plan_message), pub_from)

    async def publish_chunk_message(self, chunk: LLMResultChunk, pub_from: PublishFrom) -> None:
        """
        Publish chunk message to channel

        :param chunk: chunk
        :param pub_from: publish from
        :return:
        """
        await self.publish(QueueMessageEvent(chunk=chunk), pub_from)

    async def publish_message_end(self, llm_result: LLMResult, pub_from: PublishFrom) -> None:
        """
        Publish message end
        :param llm_result: llm result
        :param pub_from: publish from
        :return:
        """
        await self.publish(QueueMessageEndEvent(llm_result=llm_result), pub_from)
        await self.stop_listen()

    async def publish_error(self, e, code: Errcode, status: int, pub_from: PublishFrom) -> None:
        """
        Publish error
        :param e: error
        :param pub_from: publish from
        :return:
        """
        await self.publish(
            QueueErrorEvent(
                error=e,
                code=code.value,
                status=status,
            ),
            pub_from,
        )
        await self.stop_listen()

    async def publish(self, event: AppQueueEvent, pub_from: PublishFrom) -> None:
        """
        Publish event to queue
        :param event:
        :param pub_from:
        :return:
        """
        self._check_for_sqlalchemy_models(event.dict())

        message = QueueMessage(
            task_id=self._task_id,
            message_id=self._message_id,
            conversation_id=self._conversation_id,
            app_mode=self._app_mode,
            event=event,
        )

        await self._q.put(message)

        if isinstance(event, (QueueStopEvent, QueueErrorEvent, QueueMessageEndEvent)):
            await self.stop_listen()

        if pub_from == PublishFrom.APPLICATION_MANAGER and self._is_stopped():
            raise ConversationTaskStoppedError()

    @classmethod
    def set_stop_flag(cls, task_id: str, invoke_from: InvokeFrom, user_id: str) -> None:
        """
        Set task stop flag
        :return:
        """
        result = local_cache.get(cls._generate_task_belong_cache_key(task_id))
        if result is None:
            return

        user_prefix = "user"
        if result != f"{user_prefix}-{user_id}":
            return

        stopped_cache_key = cls._generate_stopped_cache_key(task_id)
        local_cache.setdefault(stopped_cache_key, 1)

    def _is_stopped(self) -> bool:
        """
        Check if task is stopped
        :return:
        """
        stopped_cache_key = ApplicationQueueManager._generate_stopped_cache_key(self._task_id)
        result = local_cache.get(stopped_cache_key)
        if result is not None:
            return True

        return False

    @classmethod
    def _generate_task_belong_cache_key(cls, task_id: str) -> str:
        """
        Generate task belong cache key
        :param task_id: task id
        :return:
        """
        return f"generate_task_belong:{task_id}"

    @classmethod
    def _generate_stopped_cache_key(cls, task_id: str) -> str:
        """
        Generate stopped cache key
        :param task_id: task id
        :return:
        """
        return f"generate_task_stopped:{task_id}"

    def _check_for_sqlalchemy_models(self, data: Any):
        # from entity to dict or list
        if isinstance(data, dict):
            for key, value in data.items():
                self._check_for_sqlalchemy_models(value)
        elif isinstance(data, list):
            for item in data:
                self._check_for_sqlalchemy_models(item)
        else:
            if isinstance(data, DeclarativeMeta) or hasattr(data, "_sa_instance_state"):
                raise TypeError(
                    "Critical Error: Passing SQLAlchemy Model instances that cause thread safety issues is not allowed."
                )

    @property
    def user_id(self):
        return self._user_id


class ConversationTaskStoppedError(Exception):
    pass
