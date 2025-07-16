import logging

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.tracking.client import ModelProviderTrackingPayload, argo_tracking
from database.provider_store import delete_provider_chosen
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from schemas.provider import AddCustomProviderSchema, DeleteCustomProviderSchema
from services.model_provider.provider_service import ProviderService


class ModelProviderHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request()
    def get(self, workspace_id: str):
        """
        ---
        tags: [Bot]
        summary: Get a list of model providers for a workspace
        description: This endpoint retrieves a list of all model providers and their \
        credentials for a specified workspace.

        responses:
            200:
                description: Successful operation
                content:
                    application/json:
                        schema:
                            ProviderListSchema

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema

        """

        try:
            model_list, not_added_list = ProviderService.get_model_provider_lists()
            self.write({"model_list": model_list, "not_added_list": not_added_list})
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("provider.get_model_providers_fail", ex=str(ex)),
                }
            )

    @RequestHandlerMixin.handle_request(AddCustomProviderSchema)
    def post(self, workspace_id: str):
        """
        ---
        tags: [Workspace]
        summary: Add a custom model provider in workspace
        description: Add custom model provider.

        requestBody:
            description: Add provider data
            required: True
            content:
                application/json:
                    schema:
                        AddCustomProviderSchema

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

        ProviderService.add_custom_provider(self.validated_data["provider"], self.validated_data["credentials"])

        argo_tracking(ModelProviderTrackingPayload(action="add"))

        return {"msg": translation_loader.translation.t("provider.model_provider_successfully_updated")}

    @RequestHandlerMixin.handle_request(DeleteCustomProviderSchema)
    def delete(self, workspace_id: str):
        """
        ---
        tags: [Workspace]
        summary: Delete a custom model provider in workspace
        description: Delete custom model provider.

        requestBody:
            description: Delete provider data
            required: True
            content:
                application/json:
                    schema:
                        DeleteCustomProviderSchema

        responses:
            200:
                description: Successful operation
                content:
                    application/json:
                        schema:
                           type: object
                           properties:
                              msg:
                                type: string

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema
        """
        provider = self.validated_data["provider"]
        delete_provider_chosen(provider)

        argo_tracking(ModelProviderTrackingPayload(action="delete"))

        return {"msg": translation_loader.translation.t("provider.provider_removed", provider=provider)}


api_router.add(r"/api/workspaces/([0-9a-zA-Z-]+)/model-providers", ModelProviderHandler)
