import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Index, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import db
from database.db import with_session

from .sqlalchemy_types import GUID


class User(db.Base):
    __tablename__ = "users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="user_pkey"),
        Index("user_email_idx", "email"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    password: Mapped[str] = mapped_column(String(255), nullable=True)
    credentials: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )


@with_session
def get_user(session: Session, user_id: str) -> Optional[User]:
    return session.query(User).get(user_id)


@with_session
def get_all_users(session: Session) -> list[User]:
    return session.query(User).all()


@with_session
def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.query(User).filter_by(email=email).first()


class GuestUser(db.Base):
    __tablename__ = "guest_users"
    __table_args__ = (PrimaryKeyConstraint("id", name="guest_user_pkey"),)

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )


@with_session
def get_guest_user(session: Session, user_id: str) -> Optional[GuestUser]:
    return session.query(GuestUser).get(user_id)
