import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Union, cast

import requests
from bs4 import BeautifulSoup
from dateutil import parser

from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import (
    ollama_get_model_list,
    ollama_model_is_embeddings,
    ollama_model_is_generation,
)
from models.model_manager import DownloadStatus
from services.auth.auth_service import get_default_user
from services.common.provider_setting_service import get_provider_setting
from services.model.model_service import ModelService
from services.model.utils import normalize_ollama_template, parse_parameters


def init():
    threading.Thread(target=period_sync_ollama, daemon=True).start()


def period_sync_ollama():
    while True:
        sync_ollama_model_info()
        time.sleep(20)


def sync_ollama_model_info():
    try:
        default_user = get_default_user()
        all_model_list = ModelService.get_undelete_model_list()

        import_complete_model_list = [
            model for model in all_model_list if model.download_status == DownloadStatus.IMPORT_COMPLETE
        ]

        all_model_ollama_map = dict(zip([model.ollama_model_name for model in all_model_list], all_model_list))
        import_complete_model_ollama_map = dict(
            zip(
                [model.ollama_model_name for model in import_complete_model_list],
                import_complete_model_list,
            )
        )

        provider_st = get_provider_setting(OLLAMA_PROVIDER)
        if not provider_st:
            return

        ollama_info = ollama_get_model_list(provider_st.safe_base_url)
        if not ollama_info:
            return
        ollama_model_list = ollama_info.models
        extra_ollama_list = [each.name for each in ollama_model_list if each.name not in all_model_ollama_map]
        extra_ollama_info = get_ollama_infos(extra_ollama_list)

        for ollama_model in ollama_model_list:
            dt = parser.isoparse(ollama_model.modified_at)
            created_at = datetime.fromtimestamp(dt.timestamp(), tz=timezone(timedelta(hours=8)))
            ollama_template = normalize_ollama_template(ollama_model.template)
            ollama_parameters = parse_parameters(ollama_model.parameters)
            general_architecture = ollama_model.model_info.general_architecture if ollama_model.model_info else None

            if model_info := all_model_ollama_map.get(ollama_model.name):
                if model_info.download_status == DownloadStatus.ALL_COMPLETE:
                    # logging.info(
                    #     f"Syncing missing architecture/template for model '{model_info.model_name}' "
                    #     f"with architecture='{ollama_model.model_info.general_architecture}' "
                    #     f"and template='{ollama_template}'."
                    # )

                    ModelService.update_model_info(
                        model_info.model_name,
                        ollama_template=ollama_template,
                        ollama_parameters=ollama_parameters,
                        ollama_architecture=general_architecture,
                    )

            if model_info := import_complete_model_ollama_map.get(ollama_model.name):
                logging.info(f"sync from ollama update info {model_info.model_name} start")
                ModelService.sync_model_info(
                    model_info.model_name,
                    ollama_model.digest,
                    model_info.category,
                    model_info.parameter,
                    ollama_model.size,
                    ollama_model.details.format,
                    ollama_model.details.quantization_level,
                    ollama_model_is_generation(model_info.model_name),
                    ollama_model_is_embeddings(model_info.model_name),
                    ollama_template=ollama_template,
                    ollama_architecture=general_architecture,
                    ollama_parameters=ollama_parameters,
                    created_at=created_at,
                    status=DownloadStatus.ALL_COMPLETE,
                )
                logging.info(f"sync from ollama update info {model_info.model_name} success")
                continue

            # if model_info := not_available_model_ollama_map.get(ollama_model.name):
            #     ModelService.sync_model_info(
            #         model_info.model_name,
            #         ollama_model.digest,
            #         ollama_model.size,
            #         ollama_model.details.format,
            #         ollama_model.details.quantization_level,
            #         ollama_model_is_generation(model_info.model_name),
            #         ollama_model_is_embeddings(model_info.model_name),
            #         status=DownloadStatus.ALL_COMPLETE
            #     )

            if (model_info := all_model_ollama_map.get(ollama_model.name)) and not model_info.digest:
                logging.info(f"model download failed but sync from ollama {model_info.model_name} start")
                ModelService.sync_model_info(
                    model_info.model_name,
                    ollama_model.digest,
                    model_info.category,
                    model_info.parameter,
                    ollama_model.size,
                    ollama_model.details.format,
                    ollama_model.details.quantization_level,
                    ollama_model_is_generation(model_info.model_name),
                    ollama_model_is_embeddings(model_info.model_name),
                    ollama_template=ollama_template,
                    ollama_architecture=general_architecture,
                    ollama_parameters=ollama_parameters,
                    created_at=created_at,
                    status=DownloadStatus.ALL_COMPLETE,
                )
                logging.info(f"model download failed but sync from ollama {model_info.model_name} success")
                continue

            if ollama_model.name in extra_ollama_list:
                logging.info(f"sync from ollama create new model: {ollama_model.name} start")
                description = extra_ollama_info.get(ollama_model.name, {}).get("description", "")
                category = extra_ollama_info.get(ollama_model.name, {}).get("category", [])
                ModelService.create_new_model(
                    ollama_model.name,
                    OLLAMA_PROVIDER,
                    ollama_model.name,
                    default_user.id,
                    ollama_model.name,
                    description=cast(str, description),
                    category=cast(list, category),
                    parameter=ollama_model.details.parameter_size,
                    quantization_level=ollama_model.details.quantization_level,
                    status=DownloadStatus.ALL_COMPLETE,
                )
                ModelService.sync_model_info(
                    ollama_model.name,
                    ollama_model.digest,
                    category,
                    ollama_model.details.parameter_size,
                    ollama_model.size,
                    ollama_model.details.format,
                    ollama_model.details.quantization_level,
                    ollama_model_is_generation(ollama_model.name),
                    ollama_model_is_embeddings(ollama_model.name),
                    ollama_template=ollama_template,
                    ollama_architecture=general_architecture,
                    ollama_parameters=ollama_parameters,
                    created_at=created_at,
                    status=DownloadStatus.ALL_COMPLETE,
                )
                logging.info(f"sync from ollama create new model: {ollama_model.name} success")
                continue

        all_complete_model_list = [
            model for model in all_model_list if model.download_status == DownloadStatus.ALL_COMPLETE
        ]
        ollama_digest_list = [model.digest for model in ollama_model_list]

        for model in all_complete_model_list:
            if model.digest not in ollama_digest_list:
                # ModelService.update_model_status(
                #     model.model_name,
                #     DownloadStatus.NOT_AVAILABLE,
                #     process_message='not available in ollama'
                # )
                ModelService.update_model_status(
                    model_name=model.model_name,
                    download_status=DownloadStatus.DELETE,
                    download_progress=0,
                    download_speed=0,
                    process_message="",
                    download_info="",
                )
                # ModelService.delete_model(model.model_name)
                logging.info(f"model delete in ollama {model.model_name}, now not available")

    except Exception as e:
        logging.exception("Failed to sync Ollama model info.")


def get_ollama_page(model_name: str) -> tuple[bool, dict[str, Union[str, list]]]:
    model_url_1 = f"https://ollama.com/library/{model_name}"
    model_url_2 = f"https://ollama.com/{model_name}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
    }

    try:
        res = requests.get(model_url_1, headers=headers, timeout=5)
        if res.status_code == 404:
            res = requests.get(model_url_2, headers=headers, timeout=5)
            if res.status_code == 404:
                logging.warning(f"[404] Model not found: {model_name}")
                return False, {
                    "model_name": model_name,
                    "description": "",
                    "category": [],
                }

        content = res.text
        soup = BeautifulSoup(content, "html.parser")

        summary = soup.find("span", id="summary-content")
        description = summary.text.strip() if summary else ""

        tag_container = soup.find("div", class_="flex flex-wrap space-x-2")
        categories = []
        if tag_container:
            for span in tag_container.find_all("span"):
                text = span.text.strip()
                if text and not text.endswith("b") and "latest" not in text.lower():
                    categories.append(text)

        return True, {
            "model_name": model_name,
            "description": description,
            "category": categories,
        }

    except Exception as ex:
        logging.warning(f"Exception fetching model page '{model_name}': {ex}")
        return True, {
            "model_name": model_name,
            "description": "",
            "category": [],
        }


def get_ollama_infos(model_names: list[str]) -> dict[str, dict[str, Union[str, list]]]:
    max_workers = 8
    temp_result: list[tuple[bool, dict[str, str | list]]] = []
    for i in range(0, len(model_names), max_workers):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            if i + max_workers < len(model_names):
                results = executor.map(get_ollama_page, model_names[i : i + max_workers])
            else:
                results = executor.map(get_ollama_page, model_names[i:])
            temp_result.extend(results)

    final_result: dict[str, dict[str, Union[str, list]]] = {}

    for result in temp_result:
        model_name = result[1]["model_name"]
        if isinstance(model_name, str):
            final_result[model_name] = result[1]

    return final_result
