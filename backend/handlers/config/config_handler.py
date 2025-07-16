from configs.env import ENABLE_MULTI_USER
from handlers.base_handler import BaseRequestHandler, RequestHandlerMixin
from handlers.router import api_router
from schemas.config import ConfigItemSchema


class ConfigHandler(BaseRequestHandler, RequestHandlerMixin):
    @RequestHandlerMixin.handle_request()
    def get(self):
        """
        ---
        tags: [Config]
        summary: Retrieve current system configuration
        description: |
          This endpoint returns the current configuration for the Argo system,
          You can use this to configure frontend features based on server capabilities.

        responses:
          200:
            description: Successful operation
            content:
              application/json:
                schema:
                  ConfigItemSchema
          400:
            description: Bad request; check `errors` for any validation issues
            content:
              application/json:
                schema:
                  BaseErrorSchema
        """

        return ConfigItemSchema().dump(
            {
                "enable_multi_user": ENABLE_MULTI_USER,
            }
        )


api_router.add("/api/config", ConfigHandler)
