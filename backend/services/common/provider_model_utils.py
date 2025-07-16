from typing import Optional

from core.entities.model_entities import APIModelCategory
from core.model_providers import model_provider_manager
from models.provider import ModelInfo, ModelProviderSetting


def fill_chat_models(
    support_chat_models: list[ModelInfo],
    const_chat_models: dict,
    custom_chat_models: list[str],
) -> list[ModelInfo]:
    available_chat_models = filter_available_models(support_chat_models, const_chat_models)
    deleted_model_names = [model.model for model in support_chat_models if model.is_deleted]
    support_model_names = {model.model: index for index, model in enumerate(available_chat_models)}
    for each_model, category in const_chat_models.items():
        if each_model in deleted_model_names:
            continue

        if each_model not in support_model_names:
            available_chat_models.append(
                ModelInfo(
                    model=each_model,
                    tags=[APIModelCategory.CHAT.value] + category,
                    chat=True,
                    embedding=False,
                )
            )
        else:
            index = support_model_names[each_model]
            if available_chat_models[index].custom:
                continue
            available_chat_models[index] = ModelInfo(
                model=each_model,
                tags=[APIModelCategory.CHAT.value] + category,
                chat=True,
                embedding=False,
            )

    for each_model in custom_chat_models:
        if each_model not in support_model_names:
            available_chat_models.append(
                ModelInfo(
                    model=each_model,
                    tags=[APIModelCategory.CHAT.value],
                    chat=True,
                    embedding=False,
                    custom=True,
                )
            )

    return deduplicate_models_by_name(available_chat_models)


def fill_embedding_models(
    support_embedding_models: list[ModelInfo],
    const_embedding_models: list[str],
    custom_embedding_models: list[str],
) -> list[ModelInfo]:
    available_embedding_models = filter_available_models(support_embedding_models, const_embedding_models)
    deleted_model_names = [model.model for model in support_embedding_models if model.is_deleted]
    support_model_names = [model.model for model in available_embedding_models]
    for each_model in const_embedding_models:
        if each_model in deleted_model_names:
            continue

        if each_model not in support_model_names:
            available_embedding_models.append(
                ModelInfo(
                    model=each_model,
                    tags=[APIModelCategory.EMBEDDING.value],
                    chat=False,
                    embedding=True,
                )
            )

    for each_model in custom_embedding_models:
        if each_model not in support_model_names:
            available_embedding_models.append(
                ModelInfo(
                    model=each_model,
                    tags=[APIModelCategory.EMBEDDING.value],
                    chat=False,
                    embedding=True,
                    custom=True,
                )
            )

    return deduplicate_models_by_name(available_embedding_models)


def fill_support_models(provider_setting: ModelProviderSetting):
    default_chat_models = model_provider_manager.get_support_chat_models(provider_setting.provider)
    default_embedding_models = model_provider_manager.get_support_embedding_models(provider_setting.provider)

    provider_setting.support_chat_models = fill_chat_models(
        provider_setting.support_chat_models or [],
        default_chat_models,
        provider_setting.custom_chat_models or [],
    )
    provider_setting.support_embedding_models = fill_embedding_models(
        provider_setting.support_embedding_models or [],
        default_embedding_models,
        provider_setting.custom_embedding_models or [],
    )

    return provider_setting


def filter_available_models(support_models, const_models: Optional[dict] | Optional[list[str]] = None):
    def is_valid(model):
        if const_models is not None:
            return model.custom or model.model in const_models
        return True

    return [model for model in support_models if is_valid(model)]


def filter_deleted_models(support_models):
    def is_valid(model):
        if getattr(model, "is_deleted", False):
            return False
        return True

    return [model for model in support_models if is_valid(model)]


def deduplicate_models_by_name(models: list[ModelInfo]) -> list[ModelInfo]:
    seen = set()
    unique_models = []
    for model in models:
        if model.model not in seen:
            seen.add(model.model)
            unique_models.append(model)
    return unique_models
