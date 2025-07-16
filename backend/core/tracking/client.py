import os
import platform
import time
import uuid
from typing import Union

import requests
from pydantic import BaseModel, Field

from configs.versions import current_version

http_session = requests.session()


class BotTrackingPayload(BaseModel):
    pass


class ChatTrackingPayload(BaseModel):
    bot_category: str = Field("")
    is_agent: bool = Field(False)
    model_provider: str = Field("")
    model_name: str = Field("")
    tools: list[dict] = Field(default_factory=list)


class ModelTrackingPayload(BaseModel):
    model_provider: str = Field("")
    model_name: str = Field("")
    status: str = Field("")
    message: str = Field("")


class ModelProviderTrackingPayload(BaseModel):
    action: str = Field("")


class KnowledgeTrackingPayload(BaseModel):
    embedding_model: str = Field("")


class DocumentTrackingPayload(BaseModel):
    pass


class FileTrackingPayload(BaseModel):
    pass


class ExceptionTrackingPayload(BaseModel):
    exception: str = Field("")


USE_ARGO_TRACKING = os.getenv("USE_ARGO_TRACKING", "false")
ARGO_TRACKING_URL = "https://api.xark-argo.com/stat/action"
REGISTER_GUEST_URL = "https://api.xark-argo.com/account/register_guest"
CACHE_TOKEN_EXPIRATION_TIME = 5 * 30 * 24 * 60 * 60
DEVICE_TYPE = 1 if platform.system() == "Darwin" else 2 if platform.system() == "Windows" else 3

cached_account = {"mid": None, "token": None, "timestamp": 0.0}  # 上次请求的时间戳


def register_guest(did: str):
    timestamp = cached_account.get("timestamp")
    if isinstance(timestamp, (int, float)) and time.time() - timestamp < CACHE_TOKEN_EXPIRATION_TIME:
        return cached_account

    try:
        response = http_session.post(
            REGISTER_GUEST_URL,
            json={
                "h_did": did,
                "h_av": current_version,
                "h_dt": DEVICE_TYPE,
                "h_app": "argo-community",
            },
            timeout=1,
        )
        response.raise_for_status()

        data = response.json()
        if response.status_code == 200 and data.get("ret") == 1:
            cached_account["mid"] = data.get("data", {}).get("mid")
            cached_account["token"] = data.get("data", {}).get("token")
            cached_account["timestamp"] = time.time()
            return cached_account
    except requests.exceptions.RequestException:
        pass

    return None


def argo_tracking(track_data: Union[dict, BaseModel]):
    try:
        if USE_ARGO_TRACKING != "true":
            return

        did = f"{uuid.getnode()}"
        account = register_guest(did)
        if not account:
            return

        action_type = "track"
        otype = "unknown"
        data = track_data
        src = "argo_app"

        if isinstance(track_data, BaseModel):
            track_type = type(track_data).__name__
            otype = track_type
            data = {"track_type": track_type, **track_data.dict()}

        payload = {
            "h_app": "argo-community",
            "h_m": account.get("mid"),
            "token": account.get("token"),
            "h_av": current_version,
            "h_dt": DEVICE_TYPE,
            "h_did": did,
            "list": [
                {
                    "action": action_type,
                    "otype": otype,
                    "id": "",
                    "oid": "",
                    "src": src,
                    "data": data,
                }
            ],
        }
        http_session.post(ARGO_TRACKING_URL, json=payload, timeout=1)
    except:
        pass
