import json
import logging
import telnetlib
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

from configs.settings import MODEL_PROVIDER_SETTINGS
from core.model_providers.ollama.types import (
    ModelInformation,
    ModelTagList,
    ResponsePayload,
)

http_session = requests.session()
first_detect = True

ollama_api_tags = "/api/tags"
ollama_api_show = "/api/show"
ollama_api_delete = "/api/delete"
ollama_api_embed = "/api/embed"
ollama_api_pull = "/api/pull"


def ollama_check_addr(base_url=None) -> str:
    if base_url is None:
        base_url = MODEL_PROVIDER_SETTINGS.get("ollama", {})["base_url"]

    try:
        ip_port = base_url.replace("http://", "").replace("https://", "")
        ip_port = ip_port.rstrip("/")
        telnetlib.Telnet(ip_port.split(":")[0], ip_port.split(":")[1], timeout=3)
        return ""
    except Exception as e:
        if isinstance(e, ConnectionRefusedError):
            error_msg = f"Ollama {base_url} is not running. Please change api url or start ollama service"
        else:
            error_msg = f"Ollama {base_url} is not running, error: {e}"

        global first_detect
        if first_detect:
            logging.warning(error_msg)
            first_detect = False
        return error_msg


def ollama_get_model_list(base_url: str) -> Optional[ModelTagList]:
    if not base_url or ollama_check_addr(base_url=base_url):
        logging.warning("Ollama base_url not found or not reachable")
        return None

    try:
        resp = http_session.get(urljoin(base_url, ollama_api_tags), timeout=5)
        if resp.status_code != 200:
            logging.error(f"Ollama API returned status code {resp.status_code}")
            return None

        model_tags = ModelTagList(**resp.json())

        for model in model_tags.models:
            try:
                model_info = ollama_get_model_info(base_url, model.name)
                if model_info:
                    model.template = model_info.template
                    model.model_info = model_info.model_info
                    model.parameters = model_info.parameters
            except Exception as e:
                logging.warning(f"[{model.name}] Failed to get model info: {e}")

        return model_tags

    except Exception as e:
        logging.exception("Exception occurred while fetching model list from Ollama.")
        return None


def ollama_alive(base_url) -> ModelTagList:
    err_msg = ollama_check_addr(base_url)
    if err_msg:
        raise Exception(err_msg)

    try:
        resp = http_session.get(urljoin(base_url, ollama_api_tags), timeout=1.5)
        if resp.status_code == 200:
            return ModelTagList(**resp.json())
        else:
            raise Exception(f"Request failed with status code {resp.status_code}")
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        raise e


def ollama_model_exist(base_url: str, model_name: str) -> bool:
    if ollama_check_addr(base_url=base_url):
        return False

    try:
        resp = http_session.get(urljoin(base_url, ollama_api_tags), timeout=3)
        if resp.status_code == 200:
            models = ModelTagList(**resp.json()).models
            for model in models:
                if model.name == model_name:
                    return True
    except Exception as e:
        logging.exception("An unexpected error occurred.")
    return False


def ollama_get_model_info(base_url: str, model_name: str) -> Optional[ModelInformation]:
    if ollama_check_addr(base_url=base_url):
        return None

    try:
        data = {
            "name": model_name,
        }
        resp = http_session.post(urljoin(base_url, ollama_api_show), json=data, timeout=5)
        if resp.status_code == 200:
            return ModelInformation(**resp.json())
        else:
            logging.error(f"Request failed with status code {resp.status_code}")
            return None
    except Exception as e:
        logging.exception("An error occurred while fetching model info from Ollama.")
        return None


def ollama_delete_model(base_url: str, model_name: str) -> bool:
    if ollama_check_addr(base_url=base_url):
        return False

    try:
        data = {
            "name": model_name,
        }
        resp = http_session.delete(urljoin(base_url, ollama_api_delete), json=data, timeout=5)
        if resp.status_code == 200:
            return True
    except Exception as e:
        logging.exception("An unexpected error occurred.")
    return False


def ollama_model_is_embeddings(model_name: str) -> bool:
    if not model_name:
        return False
    if "embed" in model_name or "bge" in model_name.lower():
        return True
    return False
    # try:
    #     data = {
    #         'model': model_name,
    #         'input': "test",
    #     }
    #     resp = http_session.post(
    #         urljoin(MODEL_PROVIDER_SETTINGS.get('ollama')['base_url'], ollama_api_embed), json=data, timeout=10)
    #
    #     if resp.status_code == 200:
    #         return True
    # except Exception as e:
    #     logging.exception(e)
    # return False


def ollama_model_is_generation(model_name: str) -> bool:
    if not model_name:
        return False
    if "emb" in model_name or "bge" in model_name.lower():
        return False
    return True


def ollama_pull_model(base_url: str, model_name: str):
    try:
        if ollama_check_addr(base_url=base_url):
            yield {"error": "ollama check fail."}
        data = {
            "name": model_name,
        }
        resp = http_session.post(urljoin(base_url, ollama_api_pull), json=data, stream=True, timeout=30)
        if resp.status_code == 200:
            for line in resp.iter_lines():
                line_info = ResponsePayload(**json.loads(line))
                if line_info.error:
                    yield {"error": line_info.error}
                if line_info.status == "success":
                    yield {"status": "success"}
                if isinstance(line_info.status, str) and "pulling" in line_info.status:
                    file_name = line_info.status.split(" ")[1]
                    yield {
                        "status": "downloading",
                        "file_name": file_name,
                        "total": line_info.total,
                        "completed": line_info.completed,
                    }
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        yield {"error": str(e)}


def ollama_create_blob(base_url: str, digest: str, file_path: Path):
    if ollama_check_addr(base_url=base_url):
        raise ValueError("Ollama is not running")

    url = f"{base_url}/api/blobs/{digest}"

    try:
        file_data = file_path.read_bytes()
        post_resp = requests.post(url, data=file_data)
        post_resp.raise_for_status()
        return True
    except Exception as e:
        logging.exception(f"Failed to upload blob {digest}")
        return False


def ollama_create_model(
    base_url: str,
    model_name: str,
    from_: Optional[str] = None,
    files: Optional[dict[str, str]] = None,
    template: Optional[str] = None,
    parameters: Optional[dict[str, Any]] = None,
):
    if ollama_check_addr(base_url=base_url):
        raise ValueError("Ollama is not running")

    if not from_ and not files:
        raise ValueError("Either 'from_' or 'files' must be specified.")

    logging.info(
        "Creating Ollama model '%s' with from:\n%s\nfiles:\n%s\ntemplate:\n%s\nparameters:\n%s",
        model_name,
        from_ or "<none>",
        files or "<none>",
        template or "<none>",
        parameters or "<none>",
    )

    payload: dict[str, Any] = {"model": model_name}

    if from_:
        payload["from"] = from_
    elif files:
        payload["files"] = files
    if template:
        payload["template"] = template
    if parameters:
        payload["parameters"] = parameters

    url = f"{base_url}/api/create"

    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    line_info = ResponsePayload(**json.loads(line))
                    if line_info.error:
                        logging.error(f"Ollama create model error: {line_info.error}")
                        return line_info.error
                    if line_info.status == "success":
                        return "success"
                except Exception as e:
                    logging.warning(f"Failed to parse response line: {line}, error: {e}")
                    continue

        raise ValueError("Unknown result: no success returned")
    except Exception as e:
        logging.exception("An unexpected error occurred while creating the model.")
        raise
