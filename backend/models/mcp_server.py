import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import db
from database.db import with_session

from .sqlalchemy_types import GUID


class ConfigType(PyEnum):
    JSON = "JSON"
    COMMAND = "COMMAND"


class CommandType(PyEnum):
    STDIO = "STDIO"
    SSE = "SSE"


class MCPStatus(PyEnum):
    NOT_READY = "not ready"
    INSTALLING = "installing"
    SUCCESS = "success"
    FAIL = "fail"


class MCPServer(db.Base):
    __tablename__ = "mcp_server_config"
    __table_args__ = (PrimaryKeyConstraint("id", name="mcp_server_pkey"),)

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    description_en: Mapped[str] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=True)
    command: Mapped[str] = mapped_column(String, nullable=True)
    command_type: Mapped[str] = mapped_column(String, default="", nullable=True)
    env: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    headers: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[], nullable=True)
    enable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    install_status: Mapped[str] = mapped_column(String, default=MCPStatus.NOT_READY.value, nullable=True)
    preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    @property
    def updated_timestamp(self):
        if self.updated_at:
            return self.updated_at.timestamp()
        return 0

    @property
    def created_timestamp(self):
        if self.created_at:
            return self.created_at.timestamp()
        return 0


@with_session
def get_server_info(session: Session, server_id) -> Optional[MCPServer]:
    return session.query(MCPServer).filter(MCPServer.id == server_id).one_or_none()
