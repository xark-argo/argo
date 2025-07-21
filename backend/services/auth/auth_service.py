import os

import bcrypt
import jwt

from configs.settings import AUTH_SETTINGS
from core.entities.user_entities import UserType
from core.errors.notfound import NotFoundError
from database import db
from models.bot import Bot, Site
from models.user import GuestUser, User, get_all_users
from services.bot.bot_service import BotService
from services.workspace.workspace_service import WorkspaceService
from utils.path import app_path

DEFAULT_EMAIL = "default@default.com"
DEFAULT_USERNAME = "default"
DEFAULT_PASSWORD = "default"


class AuthService:
    @staticmethod
    def generate_token(user, user_type: UserType = UserType.USER):
        payload = {
            "id": user.id,
            "type": user_type.value,
            # "exp": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
        }
        token = jwt.encode(
            payload,
            AUTH_SETTINGS["jwt_secret"],
            algorithm=AUTH_SETTINGS["jwt_algorithm"],
        )

        return token

    @staticmethod
    def decode_token(token):
        try:
            decoded = jwt.decode(
                token,
                AUTH_SETTINGS["jwt_secret"],
                algorithms=[AUTH_SETTINGS["jwt_algorithm"]],
            )
            return decoded
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    @staticmethod
    def login(email, password):
        with db.session_scope() as session:
            user = session.query(User).filter(User.email == email).one_or_none()
            if user and bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
                return user
        return None

    @staticmethod
    def create_guest_user_by_code(code: str) -> GuestUser:
        with db.session_scope() as session:
            site = session.query(Site).filter(Site.code == code, Site.status == "normal").first()
            if not site:
                raise NotFoundError("Site not found")

            bot = session.query(Bot).filter(Bot.id == site.bot_id).first()
            if not bot or bot.status != "normal":
                raise NotFoundError("Bot not found")

            user = GuestUser()
            session.add(user)
            session.commit()
            return user

    @staticmethod
    def register(email, username, password):
        with db.session_scope() as session:
            user = session.query(User).filter(User.email == email).one_or_none()
            if user:
                return None

            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user = User(email=email, username=username, password=hashed_password)
            session.add(user)

        space_id = WorkspaceService.create_owner_workspace_if_not_exist(user)

        conf_dir = app_path("resources", "bots")
        default_bot_list = [
            os.sep.join([conf_dir, file]) for file in sorted(os.listdir(conf_dir)) if file.endswith(".zip")
        ]
        for bot_file in default_bot_list:
            BotService.import_bot(space_id=space_id, user_id=user.id, bot_file=bot_file)

        return user


def initialize_default_user():
    default_user = AuthService.login(DEFAULT_EMAIL, DEFAULT_PASSWORD)
    if not default_user:
        AuthService.register(DEFAULT_EMAIL, DEFAULT_USERNAME, DEFAULT_PASSWORD)
        return

    default_workspaces = WorkspaceService.get_join_spaces(default_user.id)
    default_active_workspace = next((ws for ws in default_workspaces if ws.current), None)
    default_workspace_ids = {ws.id for ws in default_workspaces}

    for user in get_all_users():
        if user.email == DEFAULT_EMAIL:
            continue

        user_workspaces = WorkspaceService.get_join_spaces(user.id)
        user_active_workspace = next((ws for ws in user_workspaces if ws.current), None)

        if not user_active_workspace:
            continue

        if default_active_workspace and user_active_workspace.id == default_active_workspace.id:
            return

        if user_active_workspace.id not in default_workspace_ids:
            WorkspaceService.create_space_member(user_active_workspace, default_user, role="normal")

        WorkspaceService.switch_workspace(default_user.id, user_active_workspace.id)
        return


def get_default_user():
    return AuthService.login(DEFAULT_EMAIL, DEFAULT_PASSWORD)
