from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union, cast

import yaml


@dataclass
class ProviderInfo:
    name: str
    label: str
    class_map: dict[str, str]
    position: int
    base_url: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    color: Optional[str] = None
    parameter_rules: Optional[list[dict]] = None
    api_key_help_message: Optional[str] = None
    api_key_help_url: Optional[str] = None
    support_chat_models: dict[str, list[str]] = field(default_factory=dict)
    support_embedding_models: list[str] = field(default_factory=list)


class ProviderLoader:
    def __init__(self, base_dir: str = "core/model_providers"):
        self.base_dir = Path(base_dir)

    def load_all(self) -> dict[str, ProviderInfo]:
        providers: dict[str, ProviderInfo] = {}

        position_file = self.base_dir / "_position.yaml"
        position_order = cast(list, self._load_yaml(position_file))
        position_map = {name: idx + 1 for idx, name in enumerate(position_order)}

        for provider_dir in self.base_dir.iterdir():
            if not provider_dir.is_dir():
                continue

            provider_yaml = provider_dir / "provider.yaml"
            if not provider_yaml.exists():
                continue

            provider_cfg = cast(dict, self._load_yaml(provider_yaml))
            pname = provider_cfg["provider"]

            providers[pname] = ProviderInfo(
                name=pname,
                label=provider_cfg["label"],
                class_map=provider_cfg["class_map"],
                color=provider_cfg.get("color"),
                base_url=provider_cfg.get("base_url"),
                description=provider_cfg.get("description"),
                icon_url=provider_cfg.get("icon_url") or "/api/files/resources/icons/openai.png",
                parameter_rules=provider_cfg.get("parameter_rules", []),
                api_key_help_message=provider_cfg.get("api_key_help_message"),
                api_key_help_url=provider_cfg.get("api_key_help_url"),
                support_chat_models=provider_cfg.get("support_chat_models", {}),
                support_embedding_models=provider_cfg.get("support_embedding_models", []),
                position=position_map.get(pname) or 1000,
            )

        return providers

    def _load_yaml(self, path: Path) -> Union[list[str], dict[str, Any]]:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict) and not isinstance(data, list):
                raise ValueError(f"YAML content must be a dict, got: {type(data)}")
            return data
