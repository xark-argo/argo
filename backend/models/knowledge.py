from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BIGINT,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from configs.settings import FILE_SETTINGS
from database import db
from database.db import with_session
from models.document import DOCUMENTSTATUS

from .sqlalchemy_types import GUID


class Knowledge(db.Base):
    __tablename__ = "knowledge"
    __table_args__ = (
        Index("knowledge_user_id", "user_id"),
        Index("knowledge_name", "knowledge_name"),
    )

    collection_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    knowledge_name: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=True)
    index_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    knowledge_status: Mapped[int] = mapped_column(Integer, default=DOCUMENTSTATUS.WAITING.value, nullable=True)
    chunk_size: Mapped[int] = mapped_column(BIGINT, default=FILE_SETTINGS["CHUNK_SIZE"], nullable=True)
    chunk_overlap: Mapped[int] = mapped_column(BIGINT, default=FILE_SETTINGS["CHUNK_OVERLAP"], nullable=True)
    top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=True)
    folder: Mapped[str] = mapped_column(Text, default="", nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    update_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )


@with_session
def get_collection_by_name(session: Session, collection_name: str) -> Optional[Knowledge]:
    return session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
