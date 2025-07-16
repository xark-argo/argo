import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.db import Base, with_session

from .sqlalchemy_types import GUID


class WorkspaceStatus(str, enum.Enum):
    NORMAL = "normal"
    ARCHIVE = "archive"


class WorkspaceUserRole(enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    NORMAL = "normal"


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (PrimaryKeyConstraint("id", name="workspace_pkey"),)
    __allow_unmapped__ = True

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(255), default="normal", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    current: str


@with_session
def get_workspace(session: Session, workspace_id: str) -> Optional[Workspace]:
    return session.query(Workspace).get(workspace_id)


class WorkspaceUser(Base):
    __tablename__ = "workspace_users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="workspace_users_pkey"),
        Index("workspace_users_user_id_idx", "user_id"),
        Index("workspace_users_space_id_idx", "workspace_id"),
        UniqueConstraint("workspace_id", "user_id", name="unique_workspace_users"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(GUID, nullable=True)
    user_id: Mapped[str] = mapped_column(GUID, nullable=True)
    current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="normal", nullable=True)
    invited_by = mapped_column(GUID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )


@with_session
def has_user(session: Session, workspace_id: str, user_id: str) -> Optional[WorkspaceUser]:
    return session.query(WorkspaceUser).filter_by(workspace_id=workspace_id, user_id=user_id).first()
