import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import db
from database.db import session_scope, with_session

from .sqlalchemy_types import GUID


class Conversation(db.Base):
    __tablename__ = "conversations"
    __table_args__ = (PrimaryKeyConstraint("id", name="conversation_pkey"),)

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    bot_id: Mapped[str] = mapped_column(GUID, nullable=True)
    bot_model_config_id: Mapped[str] = mapped_column(GUID, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(255), nullable=True)
    override_model_configs: Mapped[str] = mapped_column(Text, nullable=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    introduction: Mapped[str] = mapped_column(Text, nullable=True)
    system_instruction: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(255), nullable=True)
    invoke_from: Mapped[str] = mapped_column(String(255), nullable=True)
    from_source: Mapped[str] = mapped_column(String(255), nullable=True)
    from_user_id: Mapped[str] = mapped_column(GUID, nullable=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    read_user_id: Mapped[str] = mapped_column(GUID, nullable=True)
    system_instruction_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    docs: Mapped[list[str]] = mapped_column(JSON, default=[], nullable=True)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[], nullable=True)
    datasets: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    agent_mode: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    chat_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)


@with_session
def get_conversation(session: Session, conversation_id: str) -> Optional[Conversation]:
    conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
    return conversation


class Message(db.Base):
    __tablename__ = "messages"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="message_pkey"),
        Index("message_bot_id_idx", "bot_id", "created_at"),
        Index("message_conversation_id_idx", "conversation_id"),
        Index("message_user_idx", "bot_id", "from_source", "from_user_id"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    bot_id: Mapped[str] = mapped_column(GUID, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(255), nullable=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=True)
    conversation_id: Mapped[str] = mapped_column(GUID, ForeignKey("conversations.id"), nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=True)
    message: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    message_metadata: Mapped[str] = mapped_column(Text, nullable=True)
    invoke_from: Mapped[str] = mapped_column(String(255), nullable=True)
    from_source: Mapped[str] = mapped_column(String(255), nullable=True)
    from_user_id: Mapped[str] = mapped_column(GUID, nullable=True)
    override_model_configs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[], nullable=True)
    message_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    answer_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    provider_response_latency: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    status: Mapped[str] = mapped_column(String(255), default="normal", nullable=True)
    agent_based: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_stopped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    query_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    answer_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    @property
    def agent_thoughts_dict(self):
        with session_scope() as session:
            thoughts = (
                session.query(MessageAgentThought)
                .filter(MessageAgentThought.message_id == self.id)
                .order_by(MessageAgentThought.position.asc())
                .all()
            )
            return [thought.to_dict() for thought in thoughts]

    @property
    def transform_files(self):
        new_files = []
        for file in self.files:
            if file.get("type") == "image" and file.get("transfer_method") == "local_file":
                file = {**file, "url": f"/api/documents/{file['id']}"}

            new_files.append(file)

        return new_files


@with_session
def get_message(session: Session, message_id: str) -> Optional[Message]:
    message = session.query(Message).filter(Message.id == message_id).first()
    return message


@with_session
def filter_message(
    session: Session,
    conversation_id: str,
    before_message_id: Optional[str] = None,
    message_limit: Optional[int] = None,
) -> list[Message]:
    query = session.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.is_stopped != True,
        ((Message.answer != "") | (Message.answer_deleted == True)),
    )

    if before_message_id:
        message = session.query(Message.created_at).filter(Message.id == before_message_id).first()
        if message:
            query = query.filter(Message.created_at < message.created_at)

    query = query.order_by(Message.created_at.desc())

    if message_limit and message_limit > 0:
        messages = query.limit(message_limit).all()
    else:
        messages = query.all()

    return messages


class MessageAgentThought(db.Base):
    __tablename__ = "message_agent_thoughts"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="message_agent_thought_pkey"),
        Index("message_agent_thought_message_id_idx", "message_id"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(GUID, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=True)
    thought: Mapped[str] = mapped_column(Text, nullable=True)
    tool: Mapped[str] = mapped_column(Text, nullable=True)
    tool_input: Mapped[str] = mapped_column(Text, nullable=True)
    tool_type: Mapped[str] = mapped_column(String, nullable=True)
    tool_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    tool_process_data: Mapped[str] = mapped_column(Text, nullable=True)
    tool_time_cost: Mapped[float] = mapped_column(Float, nullable=True)
    observation: Mapped[str] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    message_token: Mapped[int] = mapped_column(Integer, nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=True)
    answer_token: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(255), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=True)
    latency: Mapped[float] = mapped_column(Float, nullable=True)
    created_by_role: Mapped[str] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(GUID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)

    @property
    def tools(self) -> list[str]:
        return self.tool.split(";") if self.tool else []

    @property
    def tool_inputs_dict(self) -> dict:
        tools = self.tools
        try:
            if self.tool_input:
                data = json.loads(self.tool_input)
                result = {}
                for tool in tools:
                    if tool in data:
                        result[tool] = data[tool]
                    else:
                        if len(tools) == 1:
                            result[tool] = data
                        else:
                            result[tool] = {}
                return result
            else:
                return {tool: {} for tool in tools}
        except Exception as e:
            return {}

    @property
    def tool_outputs_dict(self) -> dict:
        tools = self.tools
        try:
            if self.observation:
                data = json.loads(self.observation)
                result = {}
                for tool in tools:
                    if tool in data:
                        result[tool] = data[tool]
                    else:
                        if len(tools) == 1:
                            result[tool] = data
                        else:
                            result[tool] = {}
                return result
            else:
                return {tool: {} for tool in tools}
        except Exception as e:
            if self.observation:
                return dict.fromkeys(tools, self.observation)
            return {}

    @property
    def retriever_resources_dict(self):
        with session_scope() as session:
            resources = (
                session.query(DatasetRetrieverResource)
                .filter(DatasetRetrieverResource.message_agent_thought_id == self.id)
                .order_by(DatasetRetrieverResource.position.asc())
                .all()
            )
            return [resource.to_dict() for resource in resources]

    def to_dict(self) -> dict:
        tool_meta = self.tool_meta or {}
        if self.tool_type == "dataset":
            tool_meta = dict(tool_meta)
            tool_meta["retriever_resources"] = self.retriever_resources_dict

        merged_metadata = {**tool_meta, **(self.meta or {})}

        return {
            "id": self.id,
            "message_id": self.message_id,
            "position": self.position,
            "thought": self.thought,
            "status": self.status,
            "observation": self.observation,
            "tool": self.tool,
            "tool_input": self.tool_input,
            "tool_type": self.tool_type,
            "metadata": merged_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@with_session
def get_agent_thoughts(session: Session, message_id: str) -> list[MessageAgentThought]:
    return (
        session.query(MessageAgentThought)
        .filter(MessageAgentThought.message_id == message_id)
        .order_by(MessageAgentThought.position.asc())
        .all()
    )


class DatasetRetrieverResource(db.Base):
    __tablename__ = "dataset_retriever_resources"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="dataset_retriever_resource_pkey"),
        Index("dataset_retriever_resource_message_id_idx", "message_id"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(GUID)
    position: Mapped[int] = mapped_column(Integer)
    message_agent_thought_id: Mapped[Optional[str]] = mapped_column(GUID)
    dataset_id: Mapped[str] = mapped_column(Text)
    dataset_name: Mapped[str] = mapped_column(Text)
    document_path: Mapped[str] = mapped_column(Text)
    document_name: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    start_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(GUID)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    def to_dict(self):
        return {
            "content": self.content,
            "score": self.score,
            "start_index": self.start_index,
            "document_path": self.document_path,
            "document_name": self.document_name,
        }
