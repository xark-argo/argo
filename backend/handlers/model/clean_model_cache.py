import os
import shutil

from configs.env import ARGO_STORAGE_PATH_TEMP_MODEL
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.model.model_service import ModelService


class CleanModelCacheHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Delete model cache
        description: Delete model cache of the provided name
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
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
          400:
            description: Invalid input
          401:
            description: Process error
        """
        model_name = self.req_dict.get("model_name")

        model = ModelService.get_model_info(model_name)
        if not model:
            self.set_status(401)
            self.write(
                {
                    "errcode": Errcode.ErrcodeRequestNotFound.value,
                    "msg": translation_loader.translation.t("model.model_not_found", model=model_name),
                }
            )
            return

        if model.download_status != DownloadStatus.ALL_COMPLETE:
            self.set_status(401)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("model.complete_model_required"),
                }
            )
            return

        if ":" in model.source:
            self.write(
                {
                    "errcode": Errcode.ErrcodeSuccess.value,
                    "msg": translation_loader.translation.t("model.ollama_no_cache_clean"),
                }
            )
            return

        source_split = model.source.split("/")
        repo_id = "/".join(source_split[0:2])
        if len(source_split) == 3:
            gguf_file = source_split[2]
            if os.path.exists(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file)):
                os.remove(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file))
        else:
            if os.path.exists(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id)):
                shutil.rmtree(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id))

        self.write(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "msg": translation_loader.translation.t("model.cache_clean_success"),
            }
        )


api_router.add("/api/model/clean_model_cache", CleanModelCacheHandler)
