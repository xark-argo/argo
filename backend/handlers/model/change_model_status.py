from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.model.model_service import ModelService


class ChangeModelStatusHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Change model status
        description: Change model status
        parameters:
          - in: body
            name: body
            description: Model details
            schema:
              type: object
              required:
                - model_name
                - status
              properties:
                model_name:
                  type: string
                status:
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
                msg:
                  type: string
          400:
            description: Invalid input
          500:
            description: Process error
        """
        model_name = self.req_dict.get("model_name")
        status = self.req_dict.get("status")
        if status not in [
            DownloadStatus.DOWNLOAD_PAUSE.value,
            DownloadStatus.DOWNLOADING.value,
        ]:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInvalidRequest.value,
                    "msg": translation_loader.translation.t("model.model_status_invalid"),
                }
            )
            return
        ModelService.update_model_status(
            model_name=model_name,
            download_status=DownloadStatus.__members__.get(status.upper()),
            download_progress=None,
            download_speed=0,
            process_message="",
            download_info="",
        )
        if status == DownloadStatus.DOWNLOAD_PAUSE.value:
            msg = translation_loader.translation.t("model.pause_download")
        else:
            msg = translation_loader.translation.t("model.resume_download")

        self.write(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "model_info": {"model_name": model_name},
                "msg": msg,
            }
        )


api_router.add("/api/model/change_model_status", ChangeModelStatusHandler)
