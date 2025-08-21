import asyncio
import logging
from typing import Optional

from core.entities.model_entities import APIModelCategory
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers import ModelMode, model_provider_manager
from core.model_providers.constants import CUSTOM_PROVIDER
from database.provider_store import update_provider_chosen
from handlers.base_handler import AppError
from models.provider import ModelInfo, ModelProviderSetting
from services.common.provider_setting_service import (
    create_provider_setting_from_info,
    get_all_provider_settings,
    get_provider_setting,
    save_or_update_provider,
)

TIMEOUT_SECONDS = 20


class ProviderService:
    @staticmethod
    async def verify_provider(provider: str, credentials: dict, model_name: Optional[str]):
        provider_st = get_provider_setting(provider)
        if not provider_st:
            raise AppError(
                f"Provider '{provider}' is not found.",
                Errcode.ErrcodeRequestNotFound,
                404,
            )

        base_url = credentials.get("base_url", "")
        api_key = credentials.get("api_key", "")

        param = {
            "base_url": base_url,
            "api_key": api_key,
            "streaming": False,
            "num_predict": 10,
            "max_tokens": 10,
            "temperature": 0,
        }

        models_to_verify = [model_name] if model_name else [m.model for m in provider_st.support_chat_models]

        last_exception: Optional[Exception] = None

        for model in models_to_verify:
            try:
                model_instance = model_provider_manager.get_model_instance(
                    provider=provider,
                    model_name=model,
                    mode=ModelMode.CHAT,
                    model_params=param,
                )

                await asyncio.wait_for(model_instance.ainvoke("ping"), timeout=TIMEOUT_SECONDS)

                provider_st.enable = 1
                provider_st.base_url = base_url
                provider_st.api_key = api_key
                save_or_update_provider(provider_st)
                return
            except asyncio.TimeoutError:
                logging.warning(
                    "Model verify timeout: provider=%s, model=%s (timeout %ss)", provider, model, TIMEOUT_SECONDS
                )
                last_exception = asyncio.TimeoutError(f"Timeout during model verify: {model}")
            except Exception as e:
                logging.warning("Model verify failed: provider=%s, model=%s, error=%s", provider, model, e)
                last_exception = e

        logging.warning("All models failed to verify.")
        raise ValueError(translation_loader.translation.t("provider.verify_fail", ex=str(last_exception)))

    @staticmethod
    def add_custom_provider(provider: str, credentials: dict):
        ProviderService._validate_custom_provider(provider, credentials)

        provider_st = create_provider_setting_from_info(
            provider, credentials.get("icon_url", ""), credentials.get("custom_name", "")
        )

        save_or_update_provider(provider_st)

    @staticmethod
    def _validate_custom_provider(provider: str, credentials: dict) -> str:
        if provider != CUSTOM_PROVIDER:
            return provider

        custom_name = credentials.get("custom_name", "")
        if not custom_name:
            raise AppError(
                translation_loader.translation.t("provider.openai_api_custom_name_required"),
                Errcode.ErrcodeInvalidRequest.value,
            )

        if custom_name in model_provider_manager.get_provider_names():
            raise AppError(
                translation_loader.translation.t("provider.custom_name_pinned_provider", custom_name=custom_name),
                Errcode.ErrcodeDuplicateOperate.value,
            )

        if any(p.custom_name == custom_name for p in get_all_provider_settings()):
            raise AppError(
                translation_loader.translation.t("provider.custom_name_duplicate"),
                Errcode.ErrcodeDuplicateOperate.value,
            )

        return provider

    @staticmethod
    def get_model_provider_lists() -> tuple[list[dict], list[dict]]:
        def build_provider_item(provider_st: ModelProviderSetting) -> dict:
            return {
                "provider": provider_st.provider,
                "label": provider_st.label or provider_st.provider,
                "custom_name": provider_st.custom_name,
                "credentials": provider_st.to_dict(),
                "enable": provider_st.enable or 0,
            }

        added_provider_list = get_all_provider_settings()

        missing_provider_list = [create_provider_setting_from_info(CUSTOM_PROVIDER)]

        model_list = [build_provider_item(p) for p in added_provider_list]
        not_added_list = [build_provider_item(p) for p in missing_provider_list]

        return model_list, not_added_list

    @staticmethod
    def add_or_update_model(provider: str, model: str, category: list[str], model_type: Optional[str] = None) -> None:
        provider_st = get_provider_setting(provider, include_deleted_models=True)
        if not provider_st:
            return

        if not model_type:
            is_embedding = APIModelCategory.EMBEDDING.value in category
        else:
            is_embedding = model_type == APIModelCategory.EMBEDDING.value

        # 先清除旧模型（embedding/chat 均清除）
        provider_st.support_embedding_models = [m for m in provider_st.support_embedding_models if m.model != model]
        provider_st.support_chat_models = [m for m in provider_st.support_chat_models if m.model != model]

        new_model = ModelInfo(
            model=model,
            tags=(category if is_embedding else list(set(category + [APIModelCategory.CHAT.value]))),
            chat=not is_embedding,
            embedding=is_embedding,
            custom=True,
        )

        if is_embedding:
            provider_st.support_embedding_models.append(new_model)
        else:
            provider_st.support_chat_models.append(new_model)

        update_provider_chosen(provider_st)

    @staticmethod
    def delete_model(provider: str, model: str) -> None:
        provider_st = get_provider_setting(provider, include_deleted_models=True)
        if not provider_st:
            raise ValueError(translation_loader.translation.t("provider.provider_not_found", provider=provider))

        def mark_model_deleted(model_list: list[ModelInfo]) -> bool:
            for model_obj in model_list:
                if model_obj.model == model:
                    model_obj.is_deleted = True
                    return True
            return False

        if mark_model_deleted(provider_st.support_chat_models) or mark_model_deleted(
            provider_st.support_embedding_models
        ):
            pass
        else:
            raise ValueError(translation_loader.translation.t("model.model_not_supported", model=model))

        update_provider_chosen(provider_st)
