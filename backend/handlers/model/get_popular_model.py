from core.errors.errcode import Errcode
from core.model_providers.constants import OLLAMA_PROVIDER
from database.provider_store import get_provider_settings_from_db
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.model.popular_model import get_cached_popular_model


class GetPopularModelHandler(BaseProtectedHandler):
    def get(self):
        self.post()

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Get popular model list
        description: Get ollama popular model list
        parameters:
          - in: body
            name: body
            description: search keyword
            schema:
              type: object
              properties:
                search_key:
                  type: string
                  description: search keyword
                  example: llama3
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                model_list:
                  type: array
                  items:
                    type: object
                    properties:
                      model_name:
                        type: string
                        description: The name of the model
                        example: abc
                      desc:
                        type: string
                        description: Description of the model
                        example: this is description
                      size:
                        type: array
                        items:
                          type: string
                        description: Available sizes
                        example: [0.5B, 7B]
          400:
            description: Invalid input
          500:
            description: Process error
        """
        model_list = get_cached_popular_model()
        provider_st = get_provider_settings_from_db(provider=OLLAMA_PROVIDER)
        base_url = provider_st["base_url"]
        if not ("localhost" in base_url or "127.0.0.1" in base_url):
            for index, each_model in enumerate(model_list):
                each_model["available"].extend(each_model["unavailable"])
                each_model["unavailable"].clear()
                model_list[index] = each_model
        self.write({"errcode": Errcode.ErrcodeSuccess.value, "model_list": model_list})


api_router.add("/api/model/get_popular_model", GetPopularModelHandler)
