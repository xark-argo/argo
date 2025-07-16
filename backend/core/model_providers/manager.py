import importlib
import logging
import os
import time
from enum import Enum
from functools import lru_cache
from typing import Any, Optional, cast

import requests
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import OpenAIEmbeddings

from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.loader import ProviderInfo, ProviderLoader
from core.model_providers.parameter import resolve_parameters
from core.model_providers.utils import extract_base_provider
from database.provider_store import get_provider_settings_from_db
from utils.path import app_path


class ModelMode(str, Enum):
    CHAT = "chat"
    GENERATE = "generate"
    EMBEDDING = "embedding"


ALL_MODELS_API = "https://api.xark-argo.com/config/default_models"


@lru_cache(maxsize=256)
def fetch_remote_provider_models(retries=3, delay=2) -> dict:
    use_remote = os.getenv("USE_REMOTE_MODELS", "").lower() == "true"
    if not use_remote:
        return {}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(ALL_MODELS_API, timeout=3)
            response.raise_for_status()
            data = response.json()
            assert isinstance(data, dict)
            return data
        except Exception as e:
            logging.warning(f"Attempt {attempt}: Failed to fetch models - {e}")
            if attempt < retries:
                time.sleep(delay)
    return {}


class ModelProviderManager:
    def __init__(self):
        self.providers_cfg: dict[str, ProviderInfo] = {}
        self.loader = ProviderLoader(base_dir=app_path("core/model_providers"))

    def load_all(self):
        self.providers_cfg = self.loader.load_all()

    def get_model_instance(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_params: Optional[dict[str, Any]] = None,
        mode: Optional[ModelMode] = None,
    ) -> BaseLanguageModel:
        if mode is None:
            mode = ModelMode.CHAT

        base_provider = extract_base_provider(provider)
        if base_provider not in self.providers_cfg:
            raise ValueError(f"Provider '{base_provider}' not found")

        if model_params and "model" in model_params:
            model_name = model_params["model"]

        if not model_name:
            raise ValueError(f"Mode name '{model_name}' not found")

        pcfg = self.providers_cfg[base_provider]

        provider_st = get_provider_settings_from_db(provider)
        if not provider_st:
            raise ValueError(f"Provider '{provider}' not initialized")

        base_url = provider_st["base_url"]
        api_key = provider_st["api_key"]
        streaming = True

        if model_params:
            base_url = model_params.get("base_url") or base_url
            api_key = model_params.get("api_key") or api_key
            streaming = model_params.get("streaming", streaming)

        resolved = resolve_parameters(pcfg.parameter_rules or [], model_params)

        kwargs = {"base_url": base_url, "api_key": api_key, "streaming": streaming, "model": model_name, **resolved}

        class_path = pcfg.class_map.get(mode.value)
        if not class_path:
            raise ValueError(f"No class mapped for mode '{mode.value}' in provider '{provider}'")

        provider_cls = self._import_class(class_path)
        instance = provider_cls(**kwargs)

        if not isinstance(instance, BaseLanguageModel):
            raise TypeError(
                f"The class '{class_path}' is not a subclass of langchain_core.language_models.BaseLanguageModel"
            )

        return cast(BaseLanguageModel, instance)

    def get_embedding_instance(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_params: Optional[dict[str, Any]] = None,
    ) -> Embeddings:
        base_provider = extract_base_provider(provider)
        if base_provider not in self.providers_cfg:
            raise ValueError(f"Provider '{base_provider}' not found")

        if model_params and "model" in model_params:
            model_name = model_params["model"]

        if not model_name:
            raise ValueError(f"Mode name '{model_name}' not found")

        pcfg = self.providers_cfg[base_provider]

        provider_st = get_provider_settings_from_db(provider)
        if not provider_st:
            raise ValueError(f"Provider '{provider}' not initialized")

        base_url = provider_st["base_url"]
        api_key = provider_st["api_key"]

        if model_params:
            base_url = model_params.get("base_url") or base_url
            api_key = model_params.get("api_key") or api_key

        kwargs = {"base_url": base_url, "model": model_name}

        if provider != OLLAMA_PROVIDER:
            kwargs["api_key"] = api_key

        class_path = pcfg.class_map.get(ModelMode.EMBEDDING.value)
        if not class_path:
            raise ValueError(f"No class mapped for mode '{ModelMode.EMBEDDING.value}' in provider '{provider}'")

        provider_cls = self._import_class(class_path)
        instance = provider_cls(**kwargs)

        if isinstance(instance, OpenAIEmbeddings):
            instance.check_embedding_ctx_length = False

        if not isinstance(instance, Embeddings):
            raise TypeError(f"The class '{class_path}' is not a subclass of langchain_core.embeddings.Embeddings")

        return cast(Embeddings, instance)

    def get_support_chat_models(self, provider_name: str) -> dict[str, list[str]]:
        base_provider = extract_base_provider(provider_name)
        remote_data = fetch_remote_provider_models().get(base_provider)
        if isinstance(remote_data, dict) and "chat_models" in remote_data:
            return cast(dict, remote_data["chat_models"])

        if provider_cfg := self.providers_cfg.get(base_provider):
            return provider_cfg.support_chat_models or {}

        return {}

    def get_support_embedding_models(self, provider_name: str) -> list[str]:
        base_provider = extract_base_provider(provider_name)
        remote_data = fetch_remote_provider_models().get(base_provider)
        if isinstance(remote_data, dict) and "embedding_models" in remote_data:
            return cast(list, remote_data["embedding_models"])

        if provider_cfg := self.providers_cfg.get(base_provider):
            return provider_cfg.support_embedding_models or []

        return []

    def get_provider_names(self) -> list[str]:
        return list(self.providers_cfg.keys())

    def get_provider_info(self, provider: str) -> Optional[ProviderInfo]:
        base_provider = extract_base_provider(provider)
        return self.providers_cfg.get(base_provider)

    def _import_class(self, class_path: str):
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
