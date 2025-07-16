import logging

from core.model_providers import model_provider_manager
from core.model_providers.constants import CUSTOM_PROVIDER
from models.provider import ModelProviderSetting
from services.common.provider_setting_service import get_all_provider_settings, save_or_update_provider, create_provider_setting_from_info
from core.model_providers.utils import extract_base_provider

from services.common.provider_model_utils import fill_support_models


def initialize_provider_settings():
    provider_list = get_all_provider_settings(include_deleted_models=True)
    provider_map = {provider_st.provider: provider_st for provider_st in provider_list}
    base_providers = {extract_base_provider(providerSt.provider) for providerSt in provider_list}

    for provider in model_provider_manager.get_provider_names():
        if provider == CUSTOM_PROVIDER:
            continue
        try:
            if provider not in base_providers:
                provider_st = create_provider_setting_from_info(provider, with_models=True)
                save_or_update_provider(provider_st)
            elif provider in provider_map:
                refresh_provider_models(provider_map[provider])
        except Exception as e:
            logging.warning(f"[init] Failed to initialize provider: {provider} - {e}")

    for provider, provider_st in provider_map.items():
        if provider.startswith(CUSTOM_PROVIDER):
            try:
                refresh_provider_models(provider_st)
            except Exception as e:
                logging.warning(f"[init] Failed to refresh custom provider: {provider} - {e}")


def refresh_provider_models(provider_st: ModelProviderSetting):
    provider_info = model_provider_manager.get_provider_info(provider_st.provider)
    if not provider_info:
        raise ValueError(f"Provider '{provider_st.provider}' is not found in loaded configuration.")

    support_chat_models = provider_st.support_chat_models or []
    support_embedding_models = provider_st.support_embedding_models or []
    current_models = {each.model for each in support_chat_models}.union(
        {each.model for each in support_embedding_models}
    )

    provider_st.position = provider_info.position
    provider_st.label = provider_info.label
    provider_st.link_msg = provider_info.api_key_help_message
    provider_st.link_url = provider_info.api_key_help_url
    provider_st.custom_chat_models = list(set(provider_st.custom_chat_models or []).difference(current_models))
    provider_st.custom_embedding_models = list(set(provider_st.custom_embedding_models or []).difference(current_models))

    provider_st = fill_support_models(provider_st)

    provider_st.custom_chat_models = []
    provider_st.custom_embedding_models = []
    save_or_update_provider(provider_st)