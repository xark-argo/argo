from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.model.model_service import ModelService


class UpdateModelNameHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Update model info
        description: Update model information
        parameters:
          - in: body
            name: body
            description: Model details
            schema:
              type: object
              required:
                - model_name
              properties:
                model_name:
                  type: string
                new_model_name:
                  type: string
                description:
                  type: string
                download_status:
                  type: string
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                model_info:
                  type: object
                  properties:
                    model_name:
                      type: string
                    description:
                      type: string
                    download_status:
                      type: string
          400:
            description: Invalid input
          500:
            description: Process error
        """
        model_name = self.req_dict.get("model_name")
        new_model_name = self.req_dict.get("new_model_name")
        description = self.req_dict.get("description")
        download_status_string = self.req_dict.get("download_status", "")
        download_status = DownloadStatus.__members__.get(download_status_string.upper())

        ok = ModelService.update_model_name(
            model_name,
            self.current_user.id,
            new_model_name,
            description,
            download_status,
        )
        if not ok:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeRequestNotFound.value,
                    "msg": translation_loader.translation.t("model.model_not_found", model=model_name),
                }
            )
            return

        self.write(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "model_info": {
                    "model_name": new_model_name,
                    "description": description,
                    "download_status": download_status_string,
                },
            }
        )


api_router.add("/api/model/update_model_name", UpdateModelNameHandler)
