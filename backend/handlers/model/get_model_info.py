from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.model.model_service import ModelService


class GetModelInfoHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["model_name"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Get model info
        description: Get model information of the provided name
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
                    id:
                      type: string
                    model_name:
                      type: string
                    ollama_model_name:
                      type: string
                    ollama_architecture:
                      type: string
                    digest:
                      type: string
                    source:
                      type: string
                    description:
                      type: string
                    size:
                      type: integer
                    model_fmt:
                      type: string
                    quantization_level:
                      type: string
                    is_generation:
                      type: boolean
                    is_embeddings:
                      type: boolean
                    download_status:
                      type: string
                      enum:
                        - download_waiting
                        - downloading
                        - download_complete
                        - convert_complete
                        - import_complete
                        - all_complete
                        - download_failed
                        - convert_failed
                        - import_failed
                        - not_available
                    download_speed:
                      type: integer
                    download_progress:
                      type: integer
                    download_info:
                      type: object
                      additionalProperties:
                        type: string
                    process_message:
                      type: string
                    updated_at:
                      type: integer
                    created_at:
                      type: integer
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
                    "msg": translation_loader.translation.t("model.model_not_found", model=model_name),
                }
            )
            return

        model_info = {
            "id": model.id,
            "model_name": model.model_name,
            "ollama_model_name": model.ollama_model_name,
            "ollama_architecture": model.ollama_architecture,
            "digest": model.digest,
            "source": model.source,
            "description": model.description,
            "size": model.size,
            "model_fmt": model.model_fmt,
            "quantization_level": model.quantization_level,
            "is_generation": model.is_generation,
            "is_embeddings": model.is_embeddings,
            "download_status": model.download_status.value,
            "download_speed": model.download_speed,
            "download_progress": model.download_progress,
            "download_info": model.download_info,
            "process_message": model.process_message,
            "updated_at": int(model.updated_at.timestamp()),
            "created_at": int(model.created_at.timestamp()),
        }
        self.write({"errcode": Errcode.ErrcodeSuccess.value, "model_info": model_info})


api_router.add("/api/model/get_model_info", GetModelInfoHandler)
