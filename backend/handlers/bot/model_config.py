from core.errors.errcode import Errcode
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from schemas.bot import UpdateModelConfigResponseSchema, UpdateModelConfigSchema
from services.bot.model_config import ModelConfigService


class ModelConfigHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(UpdateModelConfigSchema)
    def post(self):
        """
        ---
        tags: [ModelConfig]
        summary: Update model configuration
        description: Update the model configuration for a specific bot.

        requestBody:
            description: Update bot knowledge data
            required: True
            content:
                application/json:
                    schema:
                        UpdateModelConfigSchema

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                      UpdateModelConfigResponseSchema

          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        config, warning_msg = ModelConfigService.update_model_config(
            self.validated_data["bot_id"], self.validated_data["model_config"]
        )
        return UpdateModelConfigResponseSchema().dump(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "msg": "Configuration updated successfully",
                "config": config.id,
                "warning_msg": warning_msg,
            }
        )


api_router.add("/api/bot/model_config/update", ModelConfigHandler)
