import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional

from sqlalchemy import (
    BIGINT,
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base

from .sqlalchemy_types import GUID


class DownloadStatus(PyEnum):
    DOWNLOAD_WAITING = "download_waiting"
    DOWNLOADING = "downloading"
    DOWNLOAD_COMPLETE = "download_complete"
    CONVERT_COMPLETE = "convert_complete"
    IMPORT_COMPLETE = "import_complete"
    ALL_COMPLETE = "all_complete"
    DOWNLOAD_FAILED = "download_failed"
    TOO_LARGE_FAILED = "too_large_failed"
    CONVERT_FAILED = "convert_failed"
    IMPORT_FAILED = "import_failed"
    NOT_AVAILABLE = "not_available"
    DELETE = "delete"
    DOWNLOAD_PAUSE = "download_pause"
    INCOMPATIBLE = "environment_incompatible"


class Model(Base):
    __tablename__ = "models"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="model_pkey"),
        UniqueConstraint("model_name", name="unique_model_key"),
        UniqueConstraint("ollama_model_name", name="unique_ollama_key"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    model_name: Mapped[str] = mapped_column(String, nullable=True)
    ollama_model_name: Mapped[str] = mapped_column(String, nullable=True)
    ollama_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ollama_architecture: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ollama_parameters: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default={}, nullable=True)
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String, default="", nullable=True)
    digest: Mapped[str] = mapped_column(String, default="", nullable=True)
    source: Mapped[str] = mapped_column(String, default="", nullable=True)
    description: Mapped[str] = mapped_column(String, default="", nullable=True)
    category: Mapped[list[str]] = mapped_column(JSON, default=[], nullable=True)
    parameter: Mapped[str] = mapped_column(String, default="", nullable=True)
    size: Mapped[int] = mapped_column(BIGINT, default=0, nullable=True)
    model_fmt: Mapped[str] = mapped_column(String, default="", nullable=True)
    quantization_level: Mapped[str] = mapped_column(String, default="", nullable=True)
    modelfile: Mapped[str] = mapped_column(String, default="", nullable=True)
    auto_modelfile: Mapped[str] = mapped_column(String, default="", nullable=True)

    is_generation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_embeddings: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    use_xunlei: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    download_status: Mapped[DownloadStatus] = mapped_column(
        Enum(DownloadStatus), default=DownloadStatus.DOWNLOAD_WAITING, nullable=True
    )
    download_speed: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    download_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    download_info: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    process_message: Mapped[str] = mapped_column(String, default="", nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "ollama_model_name": self.ollama_model_name,
            "source": self.source,
            "quantization_level": self.quantization_level,
            "modelfile": self.modelfile,
            "auto_modelfile": self.auto_modelfile,
            "use_xunlei": self.use_xunlei,
            "size": self.size,
        }
