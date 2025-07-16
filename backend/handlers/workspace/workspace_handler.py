import logging

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.workspace.workspace_service import WorkspaceService


class WorkspaceListHandler(BaseProtectedHandler):
    def get(self):
        """
        ---
        tags:
          - Workspace
        summary: Get all workspaces
        responses:
          200:
            description: A list of spaces
            schema:
              type: object
              properties:
                id:
                  type: string
                name:
                  type: string
                current:
                  type: boolean
          400:
            description: Invalid input
        """
        try:
            spaces = WorkspaceService.get_join_spaces(self.current_user.id)

            space_list = [
                {
                    "id": space.id,
                    "name": space.name,
                    "current": space.current,
                }
                for space in spaces
            ]
            self.write({"workspaces": space_list})
        except Exception as e:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": str(e)})


class SwitchWorkspaceHandler(BaseProtectedHandler):
    def post(self):
        """
        ---
        tags:
          - Workspace
        summary: Switch the user's workspace
        description: Switch the user's current workspace to the specified workspace_id.
        parameters:
          - in: body
            name: body
            description: The workspace to switch to.
            required: true
            schema:
              type: object
              properties:
                workspace_id:
                  type: string
        responses:
          200:
            description: Successfully switched to the specified workspace.
            schema:
              type: object
              properties:
                id:
                  type: string
                name:
                  type: string
          400:
            description: Invalid input or failed to switch workspace.
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                  example: 400
                msg:
                  type: string
                  example: "Missing required field: workspace_id"
        """
        workspace_id = self.req_dict.get("workspace_id", None)

        try:
            workspace = WorkspaceService.switch_workspace(self.current_user.id, workspace_id)

            self.write(
                {
                    "id": workspace.id,
                    "name": workspace.name,
                }
            )
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("provider.switch_user_workspace_fail", ex=ex),
                }
            )


api_router.add("/api/workspace/list", WorkspaceListHandler)
api_router.add("/api/workspaces/switch", SwitchWorkspaceHandler)
