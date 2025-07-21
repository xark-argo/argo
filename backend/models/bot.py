import json
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import db
from database.db import session_scope, with_session
from utils.string_utils import generate_string

from .sqlalchemy_types import GUID


class BotCategory(PyEnum):
    ASSISTANT = "assistant"  # 标准助手类型 Bot
    ROLEPLAY = "roleplay"  # 角色扮演 Bot


class BotStatus(PyEnum):
    BOT_UNINSTALL = "uninstall"
    BOT_INSTALLING = "installing"
    BOT_NORMAL = "normal"
    BOT_FAIL = "fail"
    BOT_TO_BE_EDITED = "Unedited"


class Bot(db.Base):
    __tablename__ = "bots"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="bot_pkey"),
        Index("bot_space_id_idx", "space_id"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    space_id: Mapped[str] = mapped_column(GUID, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    icon: Mapped[str] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(255), nullable=True)
    bot_model_config_id: Mapped[str] = mapped_column(GUID, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=True)
    category: Mapped[str] = mapped_column(String(255), default=BotCategory.ASSISTANT.value, nullable=True)
    background_img: Mapped[Optional[str]] = mapped_column(String, default="", nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    status: Mapped[str] = mapped_column(String(255), default=BotStatus.BOT_NORMAL.value, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    @property
    def site(self):
        with session_scope() as session:
            site = session.query(Site).filter(Site.bot_id == self.id).first()
            return site


def get_all_bot_by_space_id(space_id: str) -> list[Bot]:
    with session_scope() as session:
        return session.query(Bot).filter(Bot.space_id == space_id).all()


def set_bot_status(bot_id: str, status: str):
    with session_scope() as session:
        bot = session.query(Bot).filter_by(id=bot_id).first()
        if bot:
            bot.status = status


@with_session
def get_bot(session: Session, bot_id: str) -> Optional[Bot]:
    return session.query(Bot).get(bot_id)


class BotModelConfig(db.Base):
    __tablename__ = "bot_model_configs"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="bot_model_config_pkey"),
        Index("bot_bot_id_idx", "bot_id"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    bot_id: Mapped[str] = mapped_column(GUID, nullable=True)
    provider: Mapped[str] = mapped_column(String(255), nullable=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=True)
    configs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    model: Mapped[str] = mapped_column(Text, nullable=True)
    user_input_form: Mapped[str] = mapped_column(Text, nullable=True)
    pre_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    advanced_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    agent_mode: Mapped[str] = mapped_column(Text, nullable=True)
    prologue: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_type: Mapped[str] = mapped_column(String(255), default="simple", nullable=True)
    network: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    tool_config: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[], nullable=True)
    plugin_config: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    silly_character: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    @property
    def model_dict(self) -> Optional[dict]:
        return json.loads(self.model) if self.model else None

    @property
    def agent_mode_dict(self) -> dict:
        return (
            json.loads(self.agent_mode)
            if self.agent_mode
            else {"enabled": False, "strategy": None, "tools": [], "prompt": None}
        )

    @property
    def user_input_form_list(self) -> list:
        return json.loads(self.user_input_form) if self.user_input_form else []

    def to_dict(self) -> dict:
        return {
            "provider": "",
            "model_id": "",
            "configs": {},
            "model": self.model_dict,
            "user_input_form": self.user_input_form_list,
            "pre_prompt": self.pre_prompt or "",
            "advanced_prompt": self.advanced_prompt or "",
            "prologue": self.prologue or "",
            "agent_mode": self.agent_mode_dict,
            "prompt_type": self.prompt_type,
            "network": self.network,
            "tool_config": self.tool_config,
            "plugin_config": self.plugin_config or {},
            "silly_character": self.silly_character or {},
        }

    def from_model_config_dict(self, model_config: dict):
        self.provider = model_config.get("provider", "")
        self.model_id = ""
        self.configs = {}
        self.model = json.dumps(model_config["model"])
        self.user_input_form = json.dumps(model_config["user_input_form"])
        self.pre_prompt = model_config["pre_prompt"]
        self.advanced_prompt = model_config["advanced_prompt"]
        self.prologue = model_config.get("prologue", "")
        self.network = model_config.get("network", False)
        self.agent_mode = json.dumps(model_config["agent_mode"])
        self.prompt_type = model_config.get("prompt_type", "simple")
        self.network = model_config.get("network", False)
        self.tool_config = model_config.get("tool_config", [])
        self.plugin_config = model_config.get("plugin_config", {})
        self.silly_character = model_config.get("silly_character", {})
        return self


@with_session
def get_model_config(session: Session, config_id: str) -> Optional[BotModelConfig]:
    return session.query(BotModelConfig).get(config_id)


class Site(db.Base):
    __tablename__ = "sites"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="site_pkey"),
        Index("site_bot_id_idx", "bot_id"),
        Index("site_code_idx", "code", "status"),
    )

    id: Mapped[str] = mapped_column(GUID, default=lambda: str(uuid.uuid4()))
    bot_id: Mapped[str] = mapped_column(GUID, nullable=True)
    status: Mapped[str] = mapped_column(String(255), default="normal", nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=True,
    )

    @staticmethod
    def generate_code(n):
        while True:
            result = generate_string(n)
            with session_scope() as session:
                while session.query(Site).filter(Site.code == result).count() > 0:
                    result = generate_string(n)

            return result
