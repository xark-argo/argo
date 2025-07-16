import threading
from concurrent.futures import ThreadPoolExecutor

from tornado.concurrent import run_on_executor

from configs.settings import MODEL_PROVIDER_SETTINGS
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.ollama.ollama_api import ollama_alive
from database.provider_store import update_ollama_provider
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.model.popular_model import refresh_popular_model
from services.model.sync_ollama import sync_ollama_model_info


class OllamaServiceCheckHandler(BaseProtectedHandler):
    executor = ThreadPoolExecutor(max_workers=10)

    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["base_url"]

    @run_on_executor
    def post(self):
        """
        ---
        tags:
          - Model
        summary: Check ollama service
        description: Check whether ollama service is available or not
        parameters:
          - in: body
            name: body
            description: Ollama url
            schema:
              type: object
              required:
                - base_url
              properties:
                base_url:
                  type: string
        responses:
          200:
            description: Ollama service available
            schema:
              type: object
              properties:
                status:
                  type: bool
          500:
            description: Ollama service check fail
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
        """
        base_url = self.req_dict.get("base_url", "")

        try:
            _ = ollama_alive(base_url)
            update_ollama_provider(base_url)
            MODEL_PROVIDER_SETTINGS["ollama"]["base_url"] = base_url
            threading.Thread(target=sync_ollama_model_info, daemon=True).start()
            threading.Thread(target=refresh_popular_model, daemon=True).start()
            self.set_status(200)
            self.write({"status": True})
        except Exception as ex:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeOllamaConnectionError.value,
                    "msg": translation_loader.translation.t("model.ollama_service_check_fail", ex=ex),
                }
            )


api_router.add("/api/model/ollama_service_check", OllamaServiceCheckHandler)
