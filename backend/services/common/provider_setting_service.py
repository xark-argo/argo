from core.model_providers import model_provider_manager
from core.model_providers.constants import CUSTOM_PROVIDER
from core.model_providers.utils import generate_custom_provider_id
from database.provider_store import get_provider_settings_from_db, update_provider_chosen
from models.provider import ModelProviderSetting
from services.common.provider_model_utils import fill_support_models, filter_deleted_models


def create_provider_setting_from_info(
    provider: str, icon: str = "", custom_name: str = "", with_models: bool = False
) -> ModelProviderSetting:
    provider_info = model_provider_manager.get_provider_info(provider)
    if not provider_info:
        raise ValueError(f"Provider '{provider}' is not found in loaded configuration.")

    provider_st = ModelProviderSetting(
        provider=provider,
        label=provider_info.label,
        custom_name=custom_name,
        description=provider_info.description,
        position=provider_info.position,
        icon_url=icon or provider_info.icon_url,
        color=provider_info.color,
        base_url=provider_info.base_url,
        origin_url=provider_info.base_url,
        link_url=provider_info.api_key_help_url,
        link_msg=provider_info.api_key_help_message,
    )

    if with_models:
        provider_st = fill_support_models(provider_st)

    return provider_st


def get_provider_setting(provider: str, include_deleted_models: bool = False) -> ModelProviderSetting | None:
    setting = get_provider_settings_from_db(provider)
    if not setting:
        return None

    provider_st = ModelProviderSetting(**setting)

    if not include_deleted_models:
        provider_st.support_chat_models = filter_deleted_models(provider_st.support_chat_models)
        provider_st.support_embedding_models = filter_deleted_models(provider_st.support_embedding_models)

    return provider_st


def get_all_provider_settings(include_deleted_models: bool = False) -> list[ModelProviderSetting]:
    settings = get_provider_settings_from_db()
    provider_list: list[ModelProviderSetting] = []

    for setting in settings:
        provider_st = ModelProviderSetting(**setting)
        if not include_deleted_models:
            provider_st.support_chat_models = filter_deleted_models(provider_st.support_chat_models)
            provider_st.support_embedding_models = filter_deleted_models(provider_st.support_embedding_models)
        provider_list.append(provider_st)

    return sorted(provider_list, key=lambda p: p.position if p.position is not None else 1000)


def save_or_update_provider(provider_setting: ModelProviderSetting):
    existing_setting = get_provider_setting(provider_setting.provider)

    if provider_setting.provider == CUSTOM_PROVIDER and provider_setting.custom_name:
        custom_name = provider_setting.custom_name.strip()
        if not existing_setting or existing_setting.custom_name != custom_name:
            provider_setting.provider = generate_custom_provider_id(custom_name)

    update_provider_chosen(provider_setting)
