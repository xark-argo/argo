from threading import Lock
from typing import Optional, Union

from tinydb import Query, TinyDB
from tinydb.table import Document

from configs.env import ARGO_STORAGE_PATH_SETTINGS
from core.model_providers.constants import OLLAMA_PROVIDER
from models.provider import ModelProviderSetting

db = TinyDB(ARGO_STORAGE_PATH_SETTINGS)

MODEL_PROVIDER_SETTINGS_TABLE = "model_provider_settings"

lock = Lock()


def update_provider_chosen(provider_st: ModelProviderSetting):
    with lock:
        settings_table = db.table(MODEL_PROVIDER_SETTINGS_TABLE)
        cond = Query().provider == provider_st.provider
        # cond = (Query().provider == providerSt.provider) & (Query().custom_name == providerSt.custom_name)
        settings = settings_table.get(cond)
        if settings:
            settings_table.update(provider_st.dict(), cond=cond)
        else:
            settings_table.insert(provider_st.dict())


def delete_provider_chosen(provider: str):
    with lock:
        settings_table = db.table(MODEL_PROVIDER_SETTINGS_TABLE)
        # cond = (Query().provider == provider) & (Query().custom_name == custom_name)
        cond = Query().provider == provider
        settings_table.remove(cond)


def get_provider_settings_from_db(provider: str = ""):
    with lock:
        settings_table = db.table(MODEL_PROVIDER_SETTINGS_TABLE)
        if provider:
            return settings_table.get(Query().provider == provider)
        else:
            return settings_table.all()


def update_ollama_provider(base_url: str):
    with lock:
        settings_table = db.table(MODEL_PROVIDER_SETTINGS_TABLE)
        doc: Optional[Union[Document, list[Document]]] = settings_table.get(Query().provider == OLLAMA_PROVIDER)

        if isinstance(doc, Document):
            doc["base_url"] = base_url
            settings_table.update(doc, Query().provider == OLLAMA_PROVIDER)
        elif isinstance(doc, list):
            for d in doc:
                d["base_url"] = base_url
                settings_table.update(d, Query().provider == OLLAMA_PROVIDER)
