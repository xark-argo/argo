import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BIGINT,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import db

from .sqlalchemy_types import GUID


class PERMISSION(Enum):
    ONLY_ME = 1
    ALL_USER = 2


class Dataset(db.Base):
    __tablename__ = "datasets"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="dataset_pkey"),
        Index("dataset_space_idx", "space_id"),
        Index("dataset_bot_idx", "bot_id"),
        Index("dataset_collection_name", "collection_name"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    space_id: Mapped[str] = mapped_column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    bot_id: Mapped[str] = mapped_column(GUID, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True)
    collection_name: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("knowledge.collection_name", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=True)
    permission: Mapped[int] = mapped_column(BIGINT, default=PERMISSION.ALL_USER.value, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )
