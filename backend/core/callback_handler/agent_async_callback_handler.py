import ast
import json
import logging
import queue
import threading
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any, Optional, TypeVar, Union
from uuid import UUID, uuid4

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage, get_buffer_string
from langchain_core.messages.tool import ToolMessage
from langchain_core.outputs import (
    ChatGeneration,
    ChatGenerationChunk,
    GenerationChunk,
    LLMResult,
)
from pydantic import BaseModel

from core.entities.application_entities import ModelConfigEntity
from core.queue.application_queue_manager import (
    ApplicationQueueManager,
    PublishFrom,
)
from database import db
from models.conversation import DatasetRetrieverResource, Message, MessageAgentThought

try:
    from langchain_core.tracers._streaming import _StreamingCallbackHandler
except ImportError:
    _StreamingCallbackHandler = object  # type: ignore

T = TypeVar("T")


def format_tool_input(input_str: str) -> str:
    """Format input as JSON string. If not valid JSON, wrap it in {"query": ...}."""
    input_str = input_str or ""
    try:
        parsed = ast.literal_eval(input_str)
    except Exception:
        parsed = {"query": input_str}
    return json.dumps(parsed, ensure_ascii=False)


DEFAULT_META_KEYS = [
    "langgraph_node",
    "knowledge_name",
    "collection_name",
    "mcp_server_name",
    "mcp_server_id",
    "error",
]


def filter_metadata(data: dict | None, keys=None) -> dict:
    if keys is None:
        keys = DEFAULT_META_KEYS
    if not data:
        return {}
    return {k: data[k] for k in keys if k in data}


class AgentLoop(BaseModel):
    id: Optional[str] = None
    position: int = 1

    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    tool_type: Optional[str] = None
    tool_started_at: Optional[float] = None
    tool_time_cost: Optional[float] = None

    metadata: Optional[dict[str, Any]] = None

    prompt: Optional[str] = None
    prompt_tokens: int = 0
    completion: Optional[str] = None
    completion_tokens: int = 0

    latency: Optional[float] = None

    status: str = "llm_started"

    started_at: Optional[float] = None


class AgentAsyncCallbackHandler(AsyncCallbackHandler, _StreamingCallbackHandler):
    """Callback Handler that prints to std out."""

    def __init__(
        self,
        model_config: ModelConfigEntity,
        message: Message,
        queue_manager: ApplicationQueueManager,
    ) -> None:
        """Initialize callback handler."""
        self.model_config = model_config
        self.queue_manager = queue_manager
        self.message = message

        self.llm = model_config.llm_instance
        self._agent_loops: dict[UUID, AgentLoop] = {}

        self.queue: queue.Queue = queue.Queue()
        self.done = threading.Event()
        self.done_error: Optional[Exception] = None

        self.seen: set[str] = set()

    def done_set(self, e: Optional[Exception] = None):
        self.done_error = e
        self.done.set()

    async def step_agent_loop(self, run_id: UUID, meta: dict[str, Any], message: BaseMessage) -> None:
        if message.id in self.seen:
            return

        loop = self._agent_loops.get(run_id)
        if loop is None:
            loop = AgentLoop(
                position=len(self._agent_loops) + 1,
                thought=str(message.content),
                metadata=filter_metadata(meta),
                started_at=time.perf_counter(),
            )

            await self._init_agent_thought(loop)
            self._agent_loops[run_id] = loop
        else:
            loop.thought = str(message.content)
            await self._complete_agent_thought(loop)

        if loop.id is None:
            return

        message.id = message.id or str(uuid4())

        self.seen.add(message.id)

        await self.queue_manager.publish_agent_thought(loop.id, PublishFrom.APPLICATION_MANAGER)

    def tap_output_aiter(self, run_id: UUID, output: AsyncIterator[T]) -> AsyncIterator[T]:
        return output

    def tap_output_iter(self, run_id: UUID, output: Iterator[T]) -> Iterator[T]:
        return output

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
        self.done.clear()

        if run_id in self._agent_loops:
            return

        loop = AgentLoop(
            position=len(self._agent_loops) + 1,
            prompt="\n".join([get_buffer_string(sub_messages) for sub_messages in messages]),
            metadata=filter_metadata(metadata, ["langgraph_node"]),
            status="llm_started",
            started_at=time.perf_counter(),
        )
        await self._init_agent_thought(loop)
        self._agent_loops[run_id] = loop

    async def on_llm_end(self, response: LLMResult, run_id: UUID, **kwargs: Any) -> None:
        if loop := self._agent_loops.get(run_id, None):
            if loop.status != "llm_started":
                return

            if loop.id is None:
                return

            now = time.perf_counter()
            loop.status = "llm_end"

            started_at = loop.started_at or now
            loop.latency = float(now - started_at)

            gen = response.generations[0][0]
            if isinstance(gen, (ChatGeneration, ChatGenerationChunk)):
                completion_message = gen.message
                additional_kwargs = completion_message.additional_kwargs or {}

                content_str: str = str(completion_message.content or "")
                tool_calls = additional_kwargs.get("tool_calls")

                if tool_calls:
                    loop.completion = json.dumps({"tool_calls": tool_calls}, ensure_ascii=False)
                    loop.thought = content_str
                else:
                    loop.completion = content_str
                    loop.thought = content_str

            generation_info = gen.generation_info or {}

            prompt_tokens: int
            completion_tokens: int

            if not generation_info.get("prompt_eval_count") or not generation_info.get("eval_count"):
                prompt = loop.prompt or ""
                completion = loop.completion or ""
                prompt_tokens = len(prompt)
                completion_tokens = len(completion)
            else:
                prompt_tokens = int(generation_info["prompt_eval_count"])
                completion_tokens = int(generation_info["eval_count"])

            loop.prompt_tokens = int(prompt_tokens)
            loop.completion_tokens = int(completion_tokens)

            await self._complete_agent_thought(loop)
            await self.queue_manager.publish_agent_thought(loop.id, PublishFrom.APPLICATION_MANAGER)

    async def on_llm_error(self, error: BaseException, run_id: UUID, **kwargs: Any) -> Any:
        logging.info("Agent on_llm_error: %s", error)
        self._agent_loops.pop(run_id, None)

    async def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        if loop := self._agent_loops.get(run_id):
            self.queue.put_nowait((loop.metadata, token))

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Union[UUID, None] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Handle the beginning of a tool execution."""
        if run_id in self._agent_loops:
            return

        loop = AgentLoop(
            position=len(self._agent_loops) + 1,
            status="tool_started",
            tool_name=serialized.get("name", "Unknown"),
            tool_input=format_tool_input(input_str),
            metadata=filter_metadata(metadata),
            started_at=time.perf_counter(),
            tool_started_at=time.perf_counter(),
        )
        if metadata:
            loop.tool_type = metadata.get("tool_type")

        await self._init_agent_thought(loop)
        self._agent_loops[run_id] = loop

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Union[UUID, None] = None,
        **kwargs: Any,
    ) -> None:
        """If not the final action, print out observation."""

        if loop := self._agent_loops.get(run_id, None):
            if loop.status != "tool_started":
                return

            if loop.id is None:
                return

            now = time.perf_counter()
            loop.status = "tool_end"

            started_at = loop.started_at or now
            tool_started_at = loop.tool_started_at or now

            loop.latency = float(now - started_at)
            loop.tool_time_cost = float(now - tool_started_at)

            if isinstance(output, ToolMessage):
                content = output.content
                if output.status == "error":
                    loop.metadata = loop.metadata or {}
                    loop.metadata["error"] = str(content)
                else:
                    loop.tool_output = str(content)
            elif isinstance(output, str):
                loop.tool_output = output

            await self._complete_agent_thought(loop)
            await self.queue_manager.publish_agent_thought(loop.id, PublishFrom.APPLICATION_MANAGER)

    async def on_query(self, query: str, metadata: Optional[dict[str, Any]]) -> None:
        pass

    async def return_retriever_resource_info(self, resource: list, run_id: UUID) -> None:
        if loop := self._agent_loops.get(run_id):
            if loop.status != "tool_started":
                return

            if resource and len(resource) > 0:
                with db.session_scope() as session:
                    for item in resource:
                        dataset_retriever_resource = DatasetRetrieverResource(
                            message_id=self.message.id,
                            message_agent_thought_id=loop.id,
                            position=item.get("position"),
                            dataset_id=item.get("dataset_id"),
                            dataset_name=item.get("dataset_name"),
                            document_path=item.get("document_path"),
                            document_name=item.get("document_name"),
                            score=item.get("score"),
                            start_index=item.get("start_index"),
                            content=item.get("content"),
                            created_by=self.message.from_user_id,
                        )
                        session.add(dataset_retriever_resource)
                        session.commit()

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Union[UUID, None] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging.info("Agent on_tool_error: %s", error)
        self._agent_loops.pop(run_id, None)

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Run on agent end."""

        # Final Answer
        if outputs == "__end__":
            self.done.set()

    async def _init_agent_thought(self, loop: AgentLoop) -> MessageAgentThought:
        with db.session_scope() as session:
            message_agent_thought = MessageAgentThought(
                message_id=self.message.id,
                position=loop.position,
                thought=loop.thought,
                tool=loop.tool_name,
                tool_input=loop.tool_input,
                tool_type=loop.tool_type,
                meta=loop.metadata,
                status=loop.status,
                message=loop.prompt,
                created_by_role="user",
                created_by=self.message.from_user_id,
            )

            session.add(message_agent_thought)
            session.commit()

            loop.id = message_agent_thought.id

        return message_agent_thought

    async def _complete_agent_thought(self, loop: AgentLoop) -> None:
        with db.session_scope() as session:
            session.query(MessageAgentThought).filter_by(id=loop.id).update(
                {
                    MessageAgentThought.observation: loop.tool_output,
                    MessageAgentThought.thought: loop.thought,
                    MessageAgentThought.answer: loop.completion,
                    MessageAgentThought.tool_process_data: "",
                    MessageAgentThought.message_token: loop.prompt_tokens,
                    MessageAgentThought.answer_token: loop.completion_tokens,
                    MessageAgentThought.status: loop.status,
                    MessageAgentThought.latency: loop.latency,
                    MessageAgentThought.meta: loop.metadata,
                    MessageAgentThought.tool_time_cost: loop.tool_time_cost,
                    MessageAgentThought.tokens: loop.prompt_tokens + loop.completion_tokens,
                }
            )
            session.commit()

    def iter(self) -> Iterator[Any]:
        while not self.queue.empty() or not self.done.is_set():
            try:
                token_or_done = self.queue.get(timeout=0.1)
                yield token_or_done
            except queue.Empty:
                if self.done.is_set():
                    break
        if self.done_error:
            raise self.done_error
