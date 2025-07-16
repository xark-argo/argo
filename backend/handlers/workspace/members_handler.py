from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from handlers.wraps import validate_uuid_param
from schemas.schemas import BaseSuccessSchema
from schemas.workspace import AddMemberSchema, DeleteMemberSchema, WorkspaceMemberSchema
from services.workspace.workspace_service import WorkspaceService


class MembersHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def get(self, workspace_id: str):
        """
        ---
        tags: [Workspace]
        summary: Get all members of current workspace.
        parameters:
          - name: workspace_id
            in: path
            required: true
            type: string

        responses:
          200:
            description: A list of members
            content:
                application/json:
                    schema:
                        WorkspaceMemberSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        users = WorkspaceService.get_workspace_members(workspace_id)
        return {"members": WorkspaceMemberSchema(many=True).dump(users)}

    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request(AddMemberSchema)
    def post(self, workspace_id: str):
        """
        ---
        tags: [Workspace]
        summary: Add member to a workspace via email
        description:
          This endpoint allows you to add member to a workspace via email.
        parameters:
          - name: workspace_id
            in: path
            required: true
            type: string
          - name: body
            in: body
            required: true
            schema:
              AddMemberSchema

        responses:
          200:
            description: User added successfully
            content:
                application/json:
                    schema:
                        BaseSuccessSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        email = self.req_dict.get("email", None)
        role = self.req_dict.get("role", None)

        WorkspaceService.add_member(self.current_user.id, workspace_id, email, role=role)
        return BaseSuccessSchema().dumps({"msg": "User added successfully"})

    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request(DeleteMemberSchema)
    def delete(self, workspace_id: str):
        """
        ---
        tags:
          - Workspace
        summary: Remove a member from a workspace
        description: Deletes a member from the specified workspace.
        parameters:
          - name: workspace_id
            in: path
            description: The ID of the workspace
            required: true
            type: string
          - name: body
            in: body
            description: JSON payload containing the user ID to remove
            required: true
            schema:
              DeleteMemberSchema

        responses:
          200:
            description: User added successfully
            content:
                application/json:
                    schema:
                        BaseSuccessSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        user_id = self.req_dict.get("user_id", None)
        WorkspaceService.remove_member(self.current_user.id, workspace_id, user_id)
        return BaseSuccessSchema().dumps(
            {"msg": translation_loader.translation.t("workspace.user_removed_successfully")}
        )


api_router.add(r"/api/workspaces/([0-9a-zA-Z-]+)/members", MembersHandler)
