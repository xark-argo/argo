import json
import time
from typing import Any, Optional, Union
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import ToolMessage, get_buffer_string
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, LLMResult

from core.callback_handler.agent_async_callback_handler import AgentLoop, filter_metadata
from core.queue.application_queue_manager import (
    ApplicationQueueManager,
    PublishFrom,
)
from database import db
from models.conversation import DatasetRetrieverResource, MessageAgentThought


class DatasetIndexToolCallbackHandler(AsyncCallbackHandler):
    """Callback handler for dataset tool."""

    def __init__(self, message_id: str, user_id: str, queue_manager: ApplicationQueueManager) -> None:
        self._queue_manager = queue_manager
        self._message_id = message_id
        self._user_id = user_id
        self._current_loop: Optional[AgentLoop] = None
        self._current_loop_status: Optional[str] = None
        self._message_agent_thought: Optional[MessageAgentThought] = None

    async def on_query(self, query: str, metadata: Optional[dict[str, Any]]) -> None:
        """
        Handle query.
        """
        if not self._current_loop:
            self._current_loop = AgentLoop(
                position=1,
                tool_name="knowledge_search",
                tool_input=json.dumps({"query": query}, ensure_ascii=False),
                tool_type="dataset",
                metadata=filter_metadata(metadata),
                started_at=time.perf_counter(),
            )
            self._current_loop_status = "tool_started"

        self._message_agent_thought = await self._init_agent_thought()

    async def return_retriever_resource_info(self, resource: list, run_id: UUID):
        if self._current_loop and self._message_agent_thought and self._current_loop_status == "tool_started":
            self._current_loop_status = "tool_end"
            if resource and len(resource) > 0:
                with db.session_scope() as session:
                    for item in resource:
                        dataset_retriever_resource = DatasetRetrieverResource(
                            message_id=self._message_agent_thought.message_id,
                            message_agent_thought_id=self._message_agent_thought.id,
                            position=item.get("position"),
                            dataset_id=item.get("dataset_id"),
                            dataset_name=item.get("dataset_name"),
                            document_path=item.get("document_path"),
                            document_name=item.get("document_name"),
                            score=item.get("score"),
                            start_index=item.get("start_index"),
                            content=item.get("content"),
                            created_by=self._user_id,
                        )
                        session.add(dataset_retriever_resource)
                        session.commit()

            self._update_agent_status(self._message_agent_thought)

            await self._queue_manager.publish_agent_thought(
                self._message_agent_thought.id, PublishFrom.APPLICATION_MANAGER
            )

            self._current_loop = None
            self._message_agent_thought = None

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Union[UUID, None] = None,
        **kwargs: Any,
    ) -> None:
        if self._current_loop and self._message_agent_thought and self._current_loop_status == "tool_started":
            if isinstance(output, ToolMessage) and output.status == "error":
                self._current_loop_status = "tool_end"
                self._current_loop.metadata = self._current_loop.metadata or {}
                self._current_loop.metadata["error"] = str(output.content)

                self._update_agent_status(self._message_agent_thought)

                await self._queue_manager.publish_agent_thought(
                    self._message_agent_thought.id, PublishFrom.APPLICATION_MANAGER
                )

                self._current_loop = None
                self._message_agent_thought = None

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list],
        *,
        run_id: UUID,
        parent_run_id: Union[UUID, None] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        if not self._current_loop and self._current_loop_status == "tool_end":
            self._current_loop = AgentLoop(
                position=2,
                prompt="\n".join([get_buffer_string(sub_messages) for sub_messages in messages]),
                started_at=time.perf_counter(),
            )
            self._current_loop_status = "llm_started"

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        if self._current_loop and self._current_loop_status == "llm_started":
            self._current_loop_status = "llm_end"

            now = time.perf_counter()
            started_at = self._current_loop.started_at or now
            self._current_loop.latency = float(now - started_at)

            gen = response.generations[0][0]
            if isinstance(gen, (ChatGeneration, ChatGenerationChunk)):
                message = gen.message
                content_str: str = str(message.content or "")
                if "reasoning_content" in message.additional_kwargs:
                    reasoning_content = message.additional_kwargs.get("reasoning_content", "")
                    if reasoning_content:
                        content_str = "<think>" + reasoning_content + "</think>" + content_str

                self._current_loop.thought = content_str
                self._message_agent_thought = await self._init_agent_thought()

            self._current_loop = None
            self._message_agent_thought = None

    async def _init_agent_thought(self) -> MessageAgentThought:
        if self._current_loop:
            with db.session_scope() as session:
                message_agent_thought = MessageAgentThought(
                    message_id=self._message_id,
                    position=self._current_loop.position,
                    thought=self._current_loop.thought,
                    tool=self._current_loop.tool_name,
                    tool_input=self._current_loop.tool_input,
                    tool_type=self._current_loop.tool_type,
                    meta=self._current_loop.metadata,
                    status=self._current_loop_status,
                    created_by_role="user",
                    created_by=self._user_id,
                )

                session.add(message_agent_thought)
                session.commit()

        await self._queue_manager.publish_agent_thought(message_agent_thought.id, PublishFrom.APPLICATION_MANAGER)

        return message_agent_thought

    def _update_agent_status(self, message_agent_thought: MessageAgentThought) -> None:
        with db.session_scope() as session:
            session.query(MessageAgentThought).filter_by(id=message_agent_thought.id).update(
                {
                    MessageAgentThought.status: self._current_loop_status,
                    MessageAgentThought.meta: self._current_loop.metadata if self._current_loop else None,
                }
            )
            session.commit()
