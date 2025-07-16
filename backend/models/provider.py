from typing import Any, Optional

from pydantic import BaseModel, Field

from core.entities.model_entities import APIModelCategory
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.model_category_style import get_model_style


class ModelInfo(BaseModel):
    model: str = Field("", description="The model name")
    tags: list[str] = Field([], description="The tags of the model")
    chat: bool = Field(False, description="Whether the model is a chat model")
    embedding: bool = Field(False, description="Whether the model is an embedding model")
    custom: bool = Field(False, description="Whether the model is a custom model")
    is_deleted: bool = Field(False, description="Whether the model is deleted")

    @classmethod
    def from_raw_list(cls, raw_list: list[dict], chat: bool, embedding: bool) -> list["ModelInfo"]:
        result = []
        for m in raw_list:
            tags = [tag.get("category") for tag in m.get("category", {}).get("category_label", {}).get("category", [])]
            result.append(
                cls(
                    model=m.get("model", ""),
                    chat=chat,
                    embedding=embedding,
                    tags=tags,
                    custom=m.get("custom", True),
                )
            )
        return result


class ModelProviderSetting(BaseModel):
    provider: str = Field("", description="The provider name")
    label: str = Field("", description="The label of the provider")
    custom_name: Optional[str] = Field("", description="The custom name of the provider")
    position: int = Field(0, description="The position of the provider")

    default_model: Optional[str] = Field("", description="The default model name")
    api_key: Optional[str] = Field("", description="The API key")
    base_url: Optional[str] = Field("", description="The base URL")
    origin_url: Optional[str] = Field("", description="The origin URL")
    support_chat_models: list[ModelInfo] = Field(default_factory=list, description="The supported chat models")
    support_embedding_models: list[ModelInfo] = Field(
        default_factory=list, description="The supported embedding models"
    )

    description: Optional[str] = Field("", description="The description of the provider")
    link_url: Optional[str] = Field("", description="The link url of the provider")
    color: Optional[str] = Field("", description="The color of the provider")
    link_msg: Optional[str] = Field("", description="The link message of the provider")
    icon_url: Optional[str] = Field("", description="The icon url of the provider")
    enable: Optional[int] = Field(0, description="The switch of the provider")

    custom_chat_models: list[str] = Field(default_factory=list, description="The custom chat models")
    custom_embedding_models: list[str] = Field(default_factory=list, description="The custom embedding models")

    @property
    def safe_base_url(self) -> str:
        if not self.base_url:
            raise ValueError(f"base_url is not set for provider '{self.provider}'")
        return self.base_url

    @property
    def safe_api_key(self) -> str:
        if self.provider == OLLAMA_PROVIDER:
            return ""

        if not self.api_key:
            raise ValueError(f"API key is required for provider '{self.provider}' but is missing or empty.")

        return self.api_key

    def to_dict(self) -> dict[str, Any]:
        support_chat_models = [
            {
                "model": each_model.model,
                "category": {
                    "extra_label": [],
                    "category_label": {
                        "type": APIModelCategory.CHAT.value,
                        "category": [
                            get_model_style(each)
                            for each in each_model.tags
                            if each in [APIModelCategory.TOOLS.value, APIModelCategory.VISION.value]
                        ],
                    },
                    "custom": each_model.custom,
                },
            }
            for each_model in self.support_chat_models or []
        ]
        support_embedding_models = [
            {
                "model": each_model.model,
                "category": {
                    "extra_label": [],
                    "category_label": {
                        "type": APIModelCategory.EMBEDDING.value,
                        "category": [
                            get_model_style(each)
                            for each in each_model.tags
                            if each == APIModelCategory.EMBEDDING.value
                        ],
                    },
                    "custom": each_model.custom,
                },
            }
            for each_model in self.support_embedding_models or []
        ]
        return {
            "provider": self.provider,
            "custom_name": self.custom_name,
            "default_model": self.default_model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "origin_url": self.origin_url,
            "support_chat_models": support_chat_models,
            "support_embedding_models": support_embedding_models,
            "description": self.description,
            "link_url": self.link_url,
            "color": self.color,
            "link_msg": self.link_msg,
            "icon_url": self.icon_url,
            "enable": self.enable,
            "custom_chat_models": [],
            "custom_embedding_models": [],
        }
