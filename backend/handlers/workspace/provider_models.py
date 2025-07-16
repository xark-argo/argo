import hashlib

from core.entities.model_entities import APIModelCategory
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.utils import CUSTOM_PROVIDER_PREFIX
from core.tracking.client import (
    ModelProviderTrackingPayload,
    ModelTrackingPayload,
    argo_tracking,
)
from database.provider_store import delete_provider_chosen, update_provider_chosen
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.common.provider_setting_service import (
    get_all_provider_settings,
    get_provider_setting,
)
from services.model_provider.provider_service import ProviderService


class ProviderModelsHandler(BaseProtectedHandler):
    def put(self, workspace_id: str):
        """
        Add Model Provider Model API

        ---
        tags:
          - Workspace
        summary: Add a model provider model
        description: This endpoint adds a new model for this provider.
        consumes:
          - application/json
        parameters:
          - in: path
            name: workspace_id
            required: true
            type: string
            description: The ID of the workspace where the model provider will be updated.
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                provider:
                  type: string
                  example: "ollama"
                  description: The name of the model provider.
                custom_name:
                  type: string
                  example: "customapi"
                  description: The custom name for the model.
                model:
                  type: string
                  example: "llama3.1"
                  description: The model name for the provider.
                category:
                  type: string
                  example: "tools"
                  description: The category of the model.
                method:
                  type: string
                  example: "add"
                  description: Add or Change model category.
        responses:
          200:
            description: Model provider successfully updated.
            schema:
              type: object
              properties:
                result:
                  type: string
                  example: "success"
          400:
            description: Bad request, invalid input data.
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Invalid provider or model."
          404:
            description: Workspace not found.
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Workspace not found."
          500:
            description: Internal server error.
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "An unexpected error occurred."
        """
        provider = self.req_dict.get("provider", None)
        if provider:
            provider = provider.lower()
            provider = provider.replace(" ", "")
        model = self.req_dict.get("model", "")
        model_type = self.req_dict.get("model_type", "")
        category = self.req_dict.get("category", [APIModelCategory.CHAT.value])
        method = self.req_dict.get("method", "add")

        if not provider:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("provider.provider_missing"),
                }
            )
            return

        provider_st = get_provider_setting(provider)
        if not provider_st:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("provider.provider_not_found", provider=provider),
                }
            )
            return

        support_chat_models_map = {each.model: each.tags for each in provider_st.support_chat_models}
        support_embedding_models_map = {each.model: each.tags for each in provider_st.support_embedding_models}
        if model in support_chat_models_map:
            cur_category = support_chat_models_map[model]
            cur_model_type = APIModelCategory.CHAT.value
        elif model in [each.model for each in provider_st.support_embedding_models]:
            cur_category = support_embedding_models_map[model]
            cur_model_type = APIModelCategory.EMBEDDING.value
        else:
            cur_category = None
            cur_model_type = None

        if method == "add":
            if cur_category:
                self.set_status(500)
                self.write({"msg": translation_loader.translation.t("model.model_already_exists", model=model)})
                return
        elif method == "change":
            if cur_category is None:
                self.set_status(500)
                self.write({"msg": translation_loader.translation.t("model.model_not_found", model=model)})
                return
            elif cur_model_type == model_type and (
                cur_category == category or cur_category == list(set(category + [APIModelCategory.CHAT.value]))
            ):
                self.set_status(500)
                self.write({"msg": translation_loader.translation.t("provider.category_not_change")})
                return

        ProviderService.add_or_update_model(provider, model, category, model_type)
        self.write({"msg": translation_loader.translation.t("provider.model_provider_successfully_updated")})

        argo_tracking(
            ModelTrackingPayload(
                model_name=model or "",
                model_provider=provider or "",
                status=method,
            )
        )

        return

    def delete(self, workspace_id: str):
        """
        Delete Model Provider Model API

        ---
        tags:
          - Workspace
        summary: Delete a model provider model
        description: This endpoint delete a model for this provider.
        consumes:
          - application/json
        parameters:
          - in: path
            name: workspace_id
            required: true
            type: string
            description: The ID of the workspace where the model provider will be updated.
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                provider:
                  type: string
                  example: "ollama"
                  description: The name of the model provider.
                custom_name:
                  type: string
                  example: "customapi"
                  description: The custom name for the model.
                model:
                  type: string
                  example: "llama3.1"
                  description: The model name for the provider.
        responses:
          200:
            description: Model provider successfully updated.
            schema:
              type: object
              properties:
                result:
                  type: string
                  example: "success"
          400:
            description: Bad request, invalid input data.
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Invalid provider or model."
          404:
            description: Workspace not found.
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Workspace not found."
          500:
            description: Internal server error.
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "An unexpected error occurred."
        """

        provider = self.req_dict.get("provider", None)
        if provider:
            provider = provider.lower()
            provider = provider.replace(" ", "")
        model = self.req_dict.get("model", "")

        try:
            ProviderService.delete_model(provider, model)
            self.write({"msg": translation_loader.translation.t("model.model_removed", model=model)})
        except Exception as e:
            self.set_status(500)
            self.write({"msg": str(e)})
            return

        argo_tracking(
            ModelTrackingPayload(
                model_name=model or "",
                model_provider=provider or "",
                status=DownloadStatus.DELETE.value,
            )
        )

    def post(self, workspace_id: str):
        provider = self.req_dict.get("provider", None)
        if provider:
            provider = provider.lower()
            provider = provider.replace(" ", "")
        custom_name = self.req_dict.get("custom_name", None)
        enable = self.req_dict.get("enable", 0)
        icon_url = self.req_dict.get("icon_url", None)

        provider_st = get_provider_setting(provider)
        if not provider_st:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("provider.provider_not_found", provider=provider),
                }
            )
            return

        if custom_name:
            provider_list = get_all_provider_settings()
            provider_names = []
            for each_provider in provider_list:
                provider_names.append(each_provider.custom_name)

            if custom_name in provider_names:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeInternalServerError.value,
                        "msg": translation_loader.translation.t("provider.custom_name_duplicate"),
                    }
                )
                return

            delete_provider_chosen(provider_st.provider)
            provider_st.custom_name = custom_name
            provider_st.icon_url = icon_url or provider_st.icon_url
            unique_id = hashlib.md5(custom_name.encode("utf-8")).hexdigest()
            provider_st.provider = f"{CUSTOM_PROVIDER_PREFIX}{unique_id}"
            update_provider_chosen(provider_st)
            self.write({"msg": translation_loader.translation.t("provider.custom_name_changed")})
        elif enable:
            if enable != provider_st.enable:
                provider_st.enable = enable
                update_provider_chosen(provider_st)
                self.write({"msg": translation_loader.translation.t("provider.custom_name_changed")})
            else:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeInternalServerError.value,
                        "msg": translation_loader.translation.t("provider.switch_not_changed"),
                    }
                )
        else:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("provider.parameter_missing"),
                }
            )
            return

        argo_tracking(ModelProviderTrackingPayload(action="update"))

        return


api_router.add(r"/api/workspaces/([0-9a-zA-Z-]+)/model_of_provider", ProviderModelsHandler)
