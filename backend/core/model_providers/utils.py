import hashlib

from core.model_providers.constants import CUSTOM_PROVIDER

CUSTOM_PROVIDER_PREFIX = f"{CUSTOM_PROVIDER}_"


def extract_base_provider(provider: str) -> str:
    if provider.startswith(CUSTOM_PROVIDER_PREFIX):
        return CUSTOM_PROVIDER

    return provider


def generate_custom_provider_id(custom_name: str, prefix: str = CUSTOM_PROVIDER_PREFIX) -> str:
    unique_id = hashlib.md5(custom_name.encode("utf-8")).hexdigest()
    return f"{prefix}{unique_id}"
