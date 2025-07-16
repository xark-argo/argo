from datetime import datetime
from enum import Enum
from typing import Union

from sqlalchemy import BIGINT, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import db
from database.db import with_session


class DOCUMENTSTATUS(Enum):
    READY = 0
    WAITING = 1
    FAIL = 2
    FINISH = 3
    DELETE = 4


class Document(db.Base):
    __tablename__ = "document"
    __table_args__ = (Index("document_collection_name", "collection_name"),)

    partition_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    collection_name: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("knowledge.collection_name", ondelete="CASCADE"),
        nullable=True,
    )
    file_id: Mapped[str] = mapped_column(String(255), ForeignKey("file.file_id", ondelete="CASCADE"), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    file_url: Mapped[str] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, nullable=True)
    file_size: Mapped[int] = mapped_column(BIGINT, default=0, nullable=True)
    content_length: Mapped[int] = mapped_column(BIGINT, default=0, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="", nullable=True)
    document_status: Mapped[int] = mapped_column(BIGINT, default=DOCUMENTSTATUS.WAITING.value, nullable=True)
    msg: Mapped[str] = mapped_column(Text, default="", nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    update_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )


@with_session
def get_partition_by_partition_name(session: Session, partition_name: str) -> Union[Document, None]:
    return session.query(Document).filter(Document.partition_name == partition_name).one_or_none()


@with_session
def get_documents_by_collection_name(session: Session, collection_name: str) -> list[Document]:
    return session.query(Document).filter(Document.collection_name == collection_name).all()
