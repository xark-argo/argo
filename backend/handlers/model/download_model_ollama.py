from typing import cast

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.model.model_service import ModelService
from services.model.sync_ollama import get_ollama_page


class DownloadModelOllamaHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Download model
        description: Download model of the provided repository
        parameters:
          - in: body
            name: body
            description: Repo details
            schema:
              type: object
              required:
                - model_name
              properties:
                model_name:
                  type: string
                size:
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
                    source:
                      type: string
                warning_msg:
                  type: string
          400:
            description: Invalid input
          500:
            description: Process error
        """
        model_name = self.req_dict.get("model_name", "")
        if not (parameter := self.req_dict.get("parameter")):
            parameter = "latest"
        parameter = parameter.replace("B", "b")
        full_model_name = ":".join([model_name, parameter])

        if not model_name.startswith("huggingface.co/"):
            flag, model_info = get_ollama_page(full_model_name)
            if not flag:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeRequestNotFound.value,
                        "msg": translation_loader.translation.t("model.model_name_invalid"),
                    }
                )
                return

        description = self.req_dict.get("description", "")
        if not description:
            description = model_info["description"]
        category = self.req_dict.get("category", {})
        if not category:
            category_info = model_info["category"]
        else:
            extra_label = category.get("extra_label", [])
            category_label = category.get("category_label", {})
            category_type = category_label.get("type")
            category_list = [each.get("category") for each in category_label.get("category")]
            category_info = list(set(category_list).union([category_type]).union(extra_label))

        model_list = ModelService.get_model_list()
        name_list = [model.model_name for model in model_list if model.download_status != DownloadStatus.DELETE]
        ollama_name_list = [
            model.ollama_model_name for model in model_list if model.download_status != DownloadStatus.DELETE
        ]

        if full_model_name in name_list or full_model_name in ollama_name_list:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeDuplicateOperate.value,
                    "msg": translation_loader.translation.t("model.duplicate_model_name"),
                }
            )
            return

        try:
            ModelService.create_new_model(
                full_model_name,
                OLLAMA_PROVIDER,
                full_model_name,
                self.current_user.id,
                full_model_name,
                description=description,
                category=cast(list[str], category_info),
                parameter=parameter,
            )
            self.write(
                {
                    "errcode": Errcode.ErrcodeSuccess.value,
                    "model_info": {
                        "model_name": full_model_name,
                        "source": full_model_name,
                    },
                    "warning_msg": "",
                }
            )
        except Exception as e:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("model.model_download_task_failed", ex=e),
                }
            )


api_router.add("/api/model/download_model_ollama", DownloadModelOllamaHandler)
