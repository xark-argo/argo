import os
import shutil

from configs.env import ARGO_STORAGE_PATH_TEMP_MODEL
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_delete_model
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.bot.bot_service import BotService
from services.common.provider_setting_service import get_provider_setting
from services.model.model_service import ModelService


class DeleteModelHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Delete model
        description: Delete model of the provided name
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

        model = ModelService.get_model_info(model_name)
        if not model:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeRequestNotFound.value,
                    "msg": translation_loader.translation.t(
                        "model.model_not_found_in_provider",
                        model=model_name,
                        provider="database",
                    ),
                }
            )
            return

        if ":" not in model.source:
            source_split = model.source.split("/")
            repo_id = "/".join(source_split[0:2])
            if len(source_split) == 3:
                gguf_file = source_split[2]
                if os.path.exists(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file)):
                    os.remove(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file))
            else:
                if os.path.exists(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id)):
                    shutil.rmtree(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id))

        all_bots = BotService.get_all_bots()
        model_name_dict = {}
        for bot in all_bots:
            bot_info = BotService.get_bot_detail(bot.id)
            chat_model_name = bot_info.get("chat_model_info", {}).get("model_name", "")
            if chat_model_name:
                model_name_dict[chat_model_name] = True
            embed_model_list = bot_info.get("embedding_model_info_list", [])
            for each in embed_model_list:
                if each["model_name"]:
                    model_name_dict[each["model_name"]] = True

        if model_name in model_name_dict:
            ModelService.update_model_status(
                model_name=model_name,
                download_status=DownloadStatus.DELETE,
                download_progress=0,
                download_speed=0,
                process_message="",
                download_info="",
            )
        else:
            ok = ModelService.delete_model(model_name)
            if not ok:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeRequestNotFound.value,
                        "msg": translation_loader.translation.t("model.model_delete_failed_in_db"),
                    }
                )
                return

        provider_st = get_provider_setting(OLLAMA_PROVIDER)
        if not provider_st:
            msg = translation_loader.translation.t(
                "provider.provider_not_found",
                provider=OLLAMA_PROVIDER,
            )
        else:
            ok = ollama_delete_model(provider_st.base_url or "", model.ollama_model_name)
            if ok:
                msg = translation_loader.translation.t("model.model_deleted_in_both")
            else:
                msg = translation_loader.translation.t("model.model_deleted_in_db_not_found_in_ollama")

        self.write(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "model_info": {"model_name": model_name},
                "msg": msg,
            }
        )


api_router.add("/api/model/delete_model", DeleteModelHandler)
