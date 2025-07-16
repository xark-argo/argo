from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from schemas.provider import VerifyProviderSchema
from services.model_provider.provider_service import ProviderService


class ProviderVerifyHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(VerifyProviderSchema)
    async def post(self, workspace_id: str):
        """
        ---
        tags: [Workspace]
        summary: Verify model provider in workspace
        description: Verify model provider.

        requestBody:
            description: Verify provider data
            required: True
            content:
                application/json:
                    schema:
                        VerifyProviderSchema

        responses:
            200:
                description: Successful operation
                content:
                    application/json:
                        schema:
                           type: object
                           properties:
                              status:
                                type: boolean

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema
        """
        await ProviderService.verify_provider(
            self.validated_data["provider"], self.validated_data["credentials"], self.validated_data.get("model_name")
        )
        return {"status": True}


api_router.add(r"/api/workspaces/([0-9a-zA-Z-]+)/provider_verify", ProviderVerifyHandler)
