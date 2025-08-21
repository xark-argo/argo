import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, Optional, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from core.entities.application_entities import (
    ApplicationGenerateEntity,
    InvokeFrom,
)
from core.prompt.prompt_message_utils import truncate_image_base64
from core.queue.application_queue_manager import ApplicationQueueManager
from core.queue.entities.llm_entities import LLMResult
from core.queue.entities.queue_entities import (
    InterruptEvent,
    PlanEvent,
    QueueAgentThoughtEvent,
    QueueErrorEvent,
    QueueMessageEndEvent,
    QueueMessageEvent,
    QueueMessageReplaceEvent,
    QueuePingEvent,
    QueueRetrieverResourcesEvent,
    QueueStopEvent,
)
from core.third_party.metrics.stream_metrics import StreamMetrics
from database import db
from models.conversation import Conversation, Message, MessageAgentThought

logger = logging.getLogger(__name__)


class TaskState(BaseModel):
    """
    TaskState entity
    """

    llm_result: LLMResult
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerateTaskPipeline:
    """
    GenerateTaskPipeline is a class that generate stream output and state management for Application.
    """

    def __init__(
        self,
        application_generate_entity: ApplicationGenerateEntity,
        queue_manager: ApplicationQueueManager,
        conversation: Conversation,
        message: Message,
    ) -> None:
        """
        Initialize GenerateTaskPipeline.
        :param application_generate_entity: application generate entity
        :param queue_manager: queue manager
        :param conversation: conversation
        :param message: message
        """
        self._application_generate_entity = application_generate_entity
        self._queue_manager = queue_manager
        self._conversation = conversation
        self._message: Message = message
        self._task_state = TaskState(
            llm_result=LLMResult(
                model=self._application_generate_entity.bot_orchestration_config_entity.bot_model_config.model,
                prompt_messages=[],
                message=AIMessage(content=""),
            )
        )

    def process(self, stream: bool) -> Union[dict, AsyncGenerator]:
        """
        Process generate task pipeline.
        :return:
        """
        if stream:
            return self._process_stream_response()
        else:
            raise NotImplementedError("This task only supports streaming output (stream=True)")

    async def _process_stream_response(self) -> AsyncGenerator:
        """
        Process stream response.
        :return:
        """
        metrics = StreamMetrics(
            RequestId=self._application_generate_entity.task_id,
            ArrivalTime=time.perf_counter(),
        )

        async for message in self._queue_manager.listen():
            event = message.event

            if isinstance(event, QueueErrorEvent):
                response = self._handle_error(event)
                yield self._yield_response(response)
                break
            elif isinstance(event, (QueueStopEvent, QueueMessageEndEvent)):
                if isinstance(event, QueueMessageEndEvent):
                    self._task_state.llm_result = event.llm_result

                metrics.finish_infer()
                metadata = {}

                metadata["ttft"] = f"{metrics.TTFT:.2f}s"
                metadata["output_speed"] = f"{metrics.OutputSpeed:.2f}tps"
                usage = self._task_state.llm_result.dict(include={"usage"})
                if usage:
                    metadata.update(usage.get("usage") or {})

                # Save message
                self._save_message(self._task_state.llm_result, metadata)

                response = {
                    "event": "message_end",
                    "task_id": self._application_generate_entity.task_id,
                    "id": self._message.id,
                    "message_id": self._message.id,
                    "metadata": metadata,
                }

                if self._conversation.mode == "chat":
                    response["conversation_id"] = self._conversation.id

                if self._task_state.metadata:
                    response["metadata"].update(self._get_response_metadata())

                yield self._yield_response(response)
            elif isinstance(event, QueueRetrieverResourcesEvent):
                self._task_state.metadata["retriever_resources"] = event.retriever_resources
            elif isinstance(event, QueueAgentThoughtEvent):
                with db.session_scope() as session:
                    agent_thought = (
                        session.query(MessageAgentThought)
                        .filter(MessageAgentThought.id == event.agent_thought_id)
                        .first()
                    )

                if agent_thought:
                    metadata = agent_thought.meta or {}
                    if agent_thought.tool_type == "dataset":
                        metadata = dict(metadata)
                        metadata["retriever_resources"] = agent_thought.retriever_resources_dict

                    response = {
                        "event": "agent_thought",
                        "id": agent_thought.id,
                        "task_id": self._application_generate_entity.task_id,
                        "message_id": self._message.id,
                        "position": agent_thought.position,
                        "thought": agent_thought.thought,
                        "observation": agent_thought.observation,
                        "status": agent_thought.status,
                        "tool": agent_thought.tool,
                        "tool_input": agent_thought.tool_input,
                        "tool_type": agent_thought.tool_type,
                        "metadata": metadata,
                        "created_at": int(self._message.created_at.timestamp()),
                    }

                    if self._conversation.mode == "chat":
                        response["conversation_id"] = self._conversation.id

                    yield self._yield_response(response)
            elif isinstance(event, QueueMessageEvent):
                chunk = event.chunk
                metrics.output_token()

                delta_text = chunk.delta.message.text()

                if not self._task_state.llm_result.prompt_messages:
                    self._task_state.llm_result.prompt_messages = chunk.prompt_messages

                content = self._task_state.llm_result.message.text()
                content += delta_text
                self._task_state.llm_result.message.content = content
                response = self._handle_chunk(delta_text)
                if chunk.delta.metadata:
                    response["metadata"] = chunk.delta.metadata

                yield self._yield_response(response)
            elif isinstance(event, InterruptEvent):
                response = {
                    "event": "interrupt",
                    "task_id": self._application_generate_entity.task_id,
                    "message_id": self._message.id,
                    "answer": event.interrupt_message,
                }
                if self._conversation.mode == "chat":
                    response["conversation_id"] = self._conversation.id

                yield self._yield_response(response)
            elif isinstance(event, PlanEvent):
                response = {
                    "event": "plan",
                    "task_id": self._application_generate_entity.task_id,
                    "message_id": self._message.id,
                    "answer": event.plan_message,
                }
                if self._conversation.mode == "chat":
                    response["conversation_id"] = self._conversation.id

                yield self._yield_response(response)
            elif isinstance(event, QueueMessageReplaceEvent):
                response = {
                    "event": "message_replace",
                    "task_id": self._application_generate_entity.task_id,
                    "message_id": self._message.id,
                    "answer": event.text,
                    "created_at": int(self._message.created_at.timestamp()),
                }

                if self._conversation.mode == "chat":
                    response["conversation_id"] = self._conversation.id

                yield self._yield_response(response)
            elif isinstance(event, QueuePingEvent):
                response = {
                    "event": "ping",
                    "task_id": self._application_generate_entity.task_id,
                    "id": self._message.id,
                    "message_id": self._message.id,
                }
                if self._conversation.mode == "chat":
                    response["conversation_id"] = self._conversation.id
                yield self._yield_response(response)
            else:
                continue

    def _save_message(self, llm_result: LLMResult, metadata: Optional[dict] = None) -> None:
        """
        Save message.
        :param llm_result: llm result
        :return:
        """
        with db.session_scope() as session:
            message = session.query(Message).filter(Message.id == self._message.id).first()
            if not message:
                return

            message.message = self._prompt_messages_to_prompt_for_saving(self._task_state.llm_result.prompt_messages)
            message.answer = str(llm_result.message.content)

            usage = llm_result.usage
            if usage:
                message.message_tokens = usage.prompt_tokens
                message.answer_tokens = usage.completion_tokens

            if metadata:
                message.message_metadata = json.dumps(metadata)

            self._message = message

            session.commit()

    def _handle_chunk(self, text: str) -> dict:
        """
        Handle completed event.
        :param text: text
        :return:
        """
        response = {
            "event": "message",
            "id": self._message.id,
            "task_id": self._application_generate_entity.task_id,
            "message_id": self._message.id,
            "answer": text,
            "created_at": int(self._message.created_at.timestamp()),
        }

        if self._conversation.mode == "chat":
            response["conversation_id"] = self._conversation.id

        return response

    def _handle_error(self, event: QueueErrorEvent) -> dict:
        """
        Handle error event.
        :param event: event
        :return:
        """
        logger.debug("error: %s", event.error)
        if event.status == 500:
            logging.error(event.error)

        response = {
            "event": "error",
            "id": self._message.id,
            "task_id": self._application_generate_entity.task_id,
            "message_id": self._message.id,
            "code": event.code,
            "message": str(event.error),
            "status": event.status,
        }

        return response

    def _get_response_metadata(self) -> dict:
        """
        Get response metadata by invoke from.
        :return:
        """
        metadata = {}

        # show_retrieve_source
        # if 'retriever_resources' in self._task_state.metadata:
        #     if self._application_generate_entity.invoke_from in [InvokeFrom.DEBUGGER, InvokeFrom.SERVICE_API]:
        #         metadata['retriever_resources'] = self._task_state.metadata['retriever_resources']
        #     else:
        #         metadata['retriever_resources'] = []
        #         for resource in self._task_state.metadata['retriever_resources']:
        #             metadata['retriever_resources'].append({
        #                 'segment_id': resource['segment_id'],
        #                 'position': resource['position'],
        #                 'document_name': resource['document_name'],
        #                 'score': resource['score'],
        #                 'content': resource['content'],
        #             })

        # show usage
        if self._application_generate_entity.invoke_from in [
            InvokeFrom.DEBUGGER,
            InvokeFrom.SERVICE_API,
        ]:
            metadata["usage"] = self._task_state.metadata["usage"]

        return metadata

    def _yield_response(self, response: dict) -> str:
        """
        Yield response.
        :param response: response
        :return:
        """
        return "data: " + json.dumps(response) + "\n\n"

    def _prompt_messages_to_prompt_for_saving(self, prompt_messages: list[BaseMessage]) -> list[dict]:
        """
        Prompt messages to prompt for saving.
        :param prompt_messages: prompt messages
        :return:
        """
        prompts = []
        for prompt_message in prompt_messages:
            if isinstance(prompt_message, HumanMessage):
                role = "user"
            elif isinstance(prompt_message, AIMessage):
                role = "assistant"
            elif isinstance(prompt_message, SystemMessage):
                role = "system"
            else:
                continue

            text = ""
            files = []
            if isinstance(prompt_message.content, list):
                for content in prompt_message.content:
                    if isinstance(content, dict):
                        if content.get("type") == "text":
                            text += "\n" + content.get("text", "")
                        elif content.get("type") == "image_url":
                            image_url = content.get("image_url", {})
                            files.append(
                                {
                                    "type": "image",
                                    "data": truncate_image_base64(image_url.get("url", "")),
                                    "detail": image_url.get("detail", ""),
                                }
                            )
                    else:
                        text += "\n" + content
            else:
                text = prompt_message.content

            prompts.append({"role": role, "text": text, "file": files})

        return prompts
