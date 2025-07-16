from core.entities.model_entities import APIModelCategory
from core.errors.errcode import Errcode
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.model.model_service import ModelService


class ChangeModelCategoryHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name", "category"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Change model category
        description: Change model category
        parameters:
          - in: body
            name: body
            description: Model details
            schema:
              type: object
              required:
                - model_name
                - category
              properties:
                model_name:
                  type: string
                category:
                  type: array
                  items:
                    type: string
                modelfile_content:
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
          500:
            description: Invalid input
        """
        model_name = self.req_dict.get("model_name", "")
        category = self.req_dict.get("category", [])
        modelfile_content = self.req_dict.get("modelfile_content", "")
        model_type = self.req_dict.get("model_type", APIModelCategory.CHAT.value)

        try:
            if model_type == APIModelCategory.CHAT.value:
                ModelService.update_model_status(
                    model_name=model_name,
                    download_status=None,
                    reset=True,
                    download_progress=None,
                    download_speed=None,
                    category=list(set(category + [model_type])),
                    is_embeddings=False,
                    is_generation=True,
                )
                ModelService.update_ollama_modelfile_and_reload_model(model_name, modelfile_content)
            else:
                ModelService.update_model_status(
                    model_name=model_name,
                    download_status=None,
                    reset=True,
                    download_progress=None,
                    download_speed=None,
                    category=category,
                    is_embeddings=True,
                    is_generation=False,
                )
            self.write({"errcode": Errcode.ErrcodeSuccess.value, "msg": ""})
        except Exception as e:
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": str(e)})


api_router.add("/api/model/change_model_category", ChangeModelCategoryHandler)
