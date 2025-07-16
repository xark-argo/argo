from typing import Optional, cast

from core.errors.notfound import NotFoundError
from database import db
from models.user import User, get_user, get_user_by_email
from models.workspace import (
    Workspace,
    WorkspaceStatus,
    WorkspaceUser,
    WorkspaceUserRole,
    get_workspace,
    has_user,
)


class WorkspaceService:
    @staticmethod
    def create_workspace(name: str) -> Workspace:
        with db.session_scope() as session:
            space = Workspace(name=name)
            session.add(space)
            return space

    @staticmethod
    def get_join_spaces(user_id: str) -> list[Workspace]:
        with db.session_scope() as session:
            query = (
                session.query(Workspace, WorkspaceUser.current)
                .join(WorkspaceUser, Workspace.id == WorkspaceUser.workspace_id)
                .filter(
                    WorkspaceUser.user_id == user_id,
                    Workspace.status == WorkspaceStatus.NORMAL,
                )
                .all()
            )

        updated_workspace = []

        for workspace, current in query:
            workspace.current = current
            updated_workspace.append(workspace)

        return updated_workspace

    @staticmethod
    def switch_workspace(user_id: str, workspace_id: Optional[str] = None) -> Workspace:
        if workspace_id is None:
            raise ValueError("Workspace ID must be provided.")

        with db.session_scope() as session:
            query = (
                session.query(WorkspaceUser, Workspace)
                .join(Workspace, WorkspaceUser.workspace_id == Workspace.id)
                .filter(
                    WorkspaceUser.user_id == user_id,
                    WorkspaceUser.workspace_id == workspace_id,
                    Workspace.status == WorkspaceStatus.NORMAL,
                )
                .first()
            )

            if not query or not query.WorkspaceUser:
                raise NotFoundError("Workspace not found or user is not in the workspace.")
            else:
                session.query(WorkspaceUser).filter(
                    WorkspaceUser.user_id == user_id,
                    WorkspaceUser.workspace_id != workspace_id,
                ).update({"current": False})
                query.WorkspaceUser.current = True
                session.commit()

        return cast(Workspace, query.Workspace)

    @staticmethod
    def get_workspace_members(workspace_id: str) -> list[User]:
        with db.session_scope() as session:
            query = (
                session.query(User, WorkspaceUser.role)
                .select_from(User)
                .join(WorkspaceUser, User.id == WorkspaceUser.user_id)
                .filter(WorkspaceUser.workspace_id == workspace_id)
            )

        # Initialize an empty list to store the updated accounts
        updated_users = []

        for user, role in query:
            user.role = role
            updated_users.append(user)

        return updated_users

    @staticmethod
    def create_owner_workspace_if_not_exist(user: User):
        with db.session_scope() as session:
            available_su = (
                session.query(WorkspaceUser)
                .filter(WorkspaceUser.user_id == user.id)
                .order_by(WorkspaceUser.id.asc())
                .first()
            )
            if available_su:
                return

        space = WorkspaceService.create_workspace(f"{user.username}'s Workspace")

        WorkspaceService.create_space_member(space, user, role="owner")

        WorkspaceService.switch_workspace(user_id=user.id, workspace_id=space.id)
        return space.id

    @staticmethod
    def create_space_member(space: Workspace, user: User, role: str = "normal") -> WorkspaceUser:
        with db.session_scope() as session:
            if role == WorkspaceUserRole.OWNER.value:
                if WorkspaceService.has_roles(space, [WorkspaceUserRole.OWNER]):
                    raise Exception("Workspace already has an owner.")

            su = WorkspaceUser(workspace_id=space.id, user_id=user.id, role=role)
            session.add(su)

        return su

    @staticmethod
    def has_roles(space: Workspace, roles: list[WorkspaceUserRole]) -> bool:
        if not all(isinstance(role, WorkspaceUserRole) for role in roles):
            raise ValueError("all roles must be SpaceUserRole")
        with db.session_scope() as session:
            return (
                session.query(WorkspaceUser)
                .filter(
                    WorkspaceUser.workspace_id == space.id,
                    WorkspaceUser.role.in_([role.value for role in roles]),
                )
                .first()
                is not None
            )

    @staticmethod
    def check_member_permission(space: Workspace, operator: User, member: User, action: str) -> None:
        perms = {
            "add": [WorkspaceUserRole.OWNER, WorkspaceUserRole.ADMIN],
            "remove": [WorkspaceUserRole.OWNER],
            "update": [WorkspaceUserRole.OWNER],
        }
        if action not in ["add", "remove", "update"]:
            raise ValueError("Invalid action.")

        if member:
            if operator.id == member.id:
                raise ValueError("Cannot operate self.")
        with db.session_scope() as session:
            ta_operator = session.query(WorkspaceUser).filter_by(workspace_id=space.id, user_id=operator.id).first()

        if not ta_operator or WorkspaceUserRole(ta_operator.role) not in perms[action]:
            raise ValueError(f"No permission to {action} member.")

    @classmethod
    def add_member(cls, operator: str, workspace_id: str, email: str, role: str = "normal"):
        user = get_user_by_email(email)
        if not user:
            raise NotFoundError("User not found.")

        inviter = get_user(operator)
        workspace = get_workspace(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.")

        WorkspaceService.check_member_permission(workspace, inviter, user, "add")

        ta = has_user(workspace_id, user.id)
        if not ta:
            WorkspaceService.create_space_member(workspace, user, role)

    @staticmethod
    def remove_member(operator_id: str, workspace_id: str, user_id: str) -> None:
        operator = get_user(operator_id)
        user = get_user(user_id)
        if not user:
            raise NotFoundError("User not found.")

        workspace = get_workspace(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found.")

        WorkspaceService.check_member_permission(workspace, operator, user, "remove")

        with db.session_scope() as session:
            ta = session.query(WorkspaceUser).filter_by(workspace_id=workspace.id, user_id=user.id).first()
            if not ta:
                raise NotFoundError("Member not in workspace.")

            session.delete(ta)
            session.commit()
