import hashlib
import io
import logging
import operator
import os
import random
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional, cast

import huggingface_hub
import psutil
import requests
from huggingface_hub import HfApi
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from configs.env import (
    ARGO_STORAGE_PATH,
    ARGO_STORAGE_PATH_TEMP_MODEL,
    EXTERNAL_ARGO_PATH,
    USE_ARGO_OLLAMA,
)
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import (
    ollama_check_addr,
    ollama_create_blob,
    ollama_create_model,
    ollama_pull_model,
)
from core.third_party.llama_cpp.llama import Llama
from core.third_party.ollama_utils.chat_template import convert_gguf_template_to_ollama
from database.provider_store import get_provider_settings_from_db
from models.model_manager import DownloadStatus, Model
from services.common.provider_setting_service import get_provider_setting
from services.doc.util import random_ua

# from services.model.convert import convert
from services.model.model_service import ModelService
from utils.gputil import get_gpus


class ThreadSafeDict:
    def __init__(self):
        self.dict = {}
        self.lock = threading.Lock()

    def set(self, key, value):
        with self.lock:
            self.dict[key] = value

    def get(self, key):
        with self.lock:
            return self.dict.get(key)

    def delete(self, key):
        with self.lock:
            if key in self.dict:
                del self.dict[key]

    def has(self, key):
        with self.lock:
            if key in self.dict:
                return True
            return False


shared_dict = ThreadSafeDict()
lock = threading.Lock()
latency_lock = threading.Lock()

site_info = {
    "https://huggingface.co/models": 999,
    "https://hf-mirror.com/models": 999,
    "https://modelscope.cn/models": 999,
}


def init():
    threading.Thread(target=process_model_download, daemon=True).start()


def process_model_download():
    while True:
        time.sleep(5)
        try:
            all_model_list = ModelService.get_model_list()
            for model in all_model_list:
                if model.download_status == DownloadStatus.ALL_COMPLETE and ":" not in model.source:
                    source_split = model.source.split("/")
                    repo_id = "/".join(source_split[0:2])
                    if len(source_split) == 3:
                        gguf_file = source_split[2]
                        if os.path.exists(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file)):
                            os.remove(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file))
                    else:
                        if os.path.exists(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id)):
                            shutil.rmtree(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id))

                if shared_dict.has(model.id):
                    time.sleep(1)
                    continue

                if model.download_status == DownloadStatus.CONVERT_COMPLETE:
                    threading.Thread(target=process_import_model, args=(model,), daemon=True).start()

                elif model.download_status == DownloadStatus.DOWNLOAD_COMPLETE:
                    threading.Thread(target=process_convert_model, args=(model,), daemon=True).start()

                elif model.download_status in [
                    DownloadStatus.DOWNLOAD_WAITING,
                    DownloadStatus.DOWNLOADING,
                ]:
                    threading.Thread(target=process_downloading_model, args=(model,), daemon=True).start()

        except Exception as e:
            logging.exception("Error occurred in process_model_download")
            continue


def register_id(func: Callable[[Model], None]):
    def wrapper(model: Model):
        with lock:
            shared_dict.set(model.id, True)

        logging.info(f"try process model: {func.__name__}, {model.model_name}")
        try:
            func(model)
        except Exception as e:
            logging.exception("An unexpected error occurred.")
        logging.info(f"process model finish: {func.__name__}, {model.model_name}")

        with lock:
            shared_dict.delete(model.id)

    return wrapper


def check_local_device(model: Model, total_size: int) -> bool:
    if total_size <= 0:
        return True

    provider_st = get_provider_settings_from_db(provider=OLLAMA_PROVIDER)
    base_url = provider_st["base_url"]
    if not ("localhost" in base_url or "127.0.0.1" in base_url):
        return True

    _, _, free_b, _ = psutil.disk_usage(ARGO_STORAGE_PATH)
    free_gb = free_b / (1024**3)
    # _, _, free_gb = ps.get_disk_usage(ARGO_STORAGE_PATH)
    total_size_gb = total_size / (1024**3)
    if total_size_gb > free_gb:
        message = translation_loader.translation.t(
            "model.insufficient_disk",
            total_size_gb=f"{total_size_gb:.2f}",
            free_gb=f"{free_gb:.2f}",
        )
        ModelService.update_model_status(
            model.model_name,
            DownloadStatus.DOWNLOAD_FAILED,
            download_progress=0,
            download_speed=0,
            process_message=message,
        )
        logging.error(message)
        return False

    total_gpu_memory_gb = sum(gpu_info.memory_total for gpu_info in get_gpus()) / 1024
    total_memory_b = psutil.virtual_memory().total
    total_memory_gb = total_memory_b / (1024**3)
    system_memory_gb = total_gpu_memory_gb + total_memory_gb - 1.0  # 1.0GB is reserved for system
    if system_memory_gb < total_size_gb:
        message = translation_loader.translation.t(
            "model.insufficient_memory",
            total_size_gb=f"{total_size_gb:.2f}",
            free_gb=f"{system_memory_gb:.2f}",
        )

        ModelService.update_model_status(
            model.model_name,
            DownloadStatus.DOWNLOAD_FAILED,
            download_progress=0,
            download_speed=0,
            process_message=message,
        )
        logging.warning(message)
        return False
    return True


def process_downloading_model_ollama(model: Model):
    ModelService.update_model_status(
        model.model_name,
        DownloadStatus.DOWNLOADING,
        download_progress=0,
        download_speed=0,
    )

    provider_st = get_provider_setting(OLLAMA_PROVIDER)
    base_url = provider_st.base_url or "" if provider_st else ""

    start_time, start_size = time.time(), 0
    for status in ollama_pull_model(base_url, model.source):
        if err := status.get("error"):
            if ollama_check_addr():
                msg = translation_loader.translation.t("model.ollama_service_unavailable")
            else:
                msg = translation_loader.translation.t("model.service_connection_failed")
            ModelService.update_model_status(
                model.model_name,
                DownloadStatus.DOWNLOAD_FAILED,
                download_progress=0,
                download_speed=0,
                process_message=msg,
            )
            logging.info(f"download {model.model_name} error: {err}")
            return

        if status.get("status") == "success":
            ModelService.update_model_status(
                model.model_name,
                DownloadStatus.IMPORT_COMPLETE,
                download_progress=100,
                download_speed=0,
                process_message=translation_loader.translation.t("model.download_info.download_complete"),
            )
            logging.info(f"download {model.model_name} all success")
            return

        if status.get("status") == "downloading":
            download_size, total_size = (
                status.get("completed", 0),
                status.get("total", 0),
            )

            if not check_local_device(model, total_size):
                return

            sub_time, start_time = (time.time() - start_time), time.time()
            sub_size, start_size = download_size - start_size, download_size
            speed = sub_size // (sub_time + 1e-7) if sub_size > 0 else 0
            download_progress = 100 * download_size // total_size if download_size > 0 and total_size > 0 else None

            ok = ModelService.update_model_status(
                model.model_name,
                DownloadStatus.DOWNLOADING,
                reset=True,
                download_progress=download_progress,
                download_speed=speed,
                process_message=translation_loader.translation.t(
                    "model.download_info.download_size",
                    cur_size=download_size // (1024 * 1024),
                    total_size=total_size // (1024 * 1024),
                ),
            )
            if random.random() < 0.2:
                logging.info(
                    f"downloading {model.model_name}/{status.get('file_name', 'main')}: "
                    f"{download_size}/{total_size}, speed: {speed}"
                )
            if not ok:
                logging.info("Model download interrupted.")
                return


def process_downloading_model_huggingface(model: Model):
    ModelService.update_model_status(
        model.model_name,
        DownloadStatus.DOWNLOADING,
        download_progress=0,
        download_speed=0,
    )
    source_split = model.source.split("/")
    repo_id, gguf_file = "/".join(source_split[0:2]), None
    if len(source_split) == 3:
        gguf_file = source_split[2]

    if gguf_file:
        file_list = [gguf_file]
    else:
        file_list = [f.rfilename for f in HfApi().repo_info(repo_id).siblings or []]

    for file in file_list:
        storage_path = os.path.dirname(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, file))
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)

    big_file_list = [file for file in file_list if file.split(".")[-1] in ["safetensors", "gguf", "bin", "onnx"]]
    other_file_list = [file for file in file_list if file not in big_file_list]
    big_file_size_list, big_file_local_size_list = (
        [0] * len(big_file_list),
        [0] * len(big_file_list),
    )

    for i, file in enumerate(big_file_list):
        file_url = huggingface_hub.hf_hub_url(repo_id, file)
        local_file_path = os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, file)

        response = requests.get(file_url, stream=True)
        big_file_size_list[i] = int(response.headers.get("content-length", 0))
        if os.path.exists(local_file_path):
            big_file_local_size_list[i] = os.path.getsize(local_file_path)

    download_size = sum(big_file_local_size_list)
    total_size = sum(big_file_size_list)
    download_progress = 100 * download_size // total_size if total_size != 0 else None

    if not check_local_device(model, total_size):
        return

    ok = ModelService.update_model_status(
        model.model_name,
        DownloadStatus.DOWNLOADING,
        reset=True,
        download_progress=download_progress,
        download_speed=0,
        process_message=translation_loader.translation.t(
            "model.download_info.download_size",
            cur_size=download_size // (1024 * 1024),
            total_size=total_size // (1024 * 1024),
        ),
    )
    logging.info(f"downloading {model.model_name}: {download_size}/{total_size}, speed: 0")
    if not ok:
        logging.info("Model download interrupted.")
        return

    scope_flag = False
    model_scope_key = f"https://modelscope.cn/api/v1/models/{repo_id}/revisions"
    res = requests.get(model_scope_key, headers={"User-Agent": random_ua()})
    if res.status_code == 200:
        scope_flag = True

    for file in other_file_list:
        file_url = huggingface_hub.hf_hub_url(repo_id, file)
        file_url = get_file_url(file_url, scope_flag)
        logging.info(f"process_downloading_model_huggingface file_url: {file_url}")
        response = requests.get(file_url, timeout=10)
        other_file_path = Path(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, file))
        other_file_path.write_bytes(response.content)

    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[443, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    file_buffer = io.BytesIO()
    for i, file in enumerate(big_file_list):
        origin_file_url = huggingface_hub.hf_hub_url(repo_id, file)
        local_file_path = os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, file)

        max_retries = 5
        with open(local_file_path, "ab") as fp:
            big_file_local_size_list[i] = fp.tell()
            for retry_num in range(max_retries):
                get_site_latency()
                file_url = get_file_url(origin_file_url, scope_flag)
                logging.info(f"process_downloading_model_huggingface file_url: {file_url}")
                try:
                    file_buffer.seek(0)
                    file_buffer.truncate(0)
                    with session.get(
                        file_url,
                        stream=True,
                        timeout=(10, 120),
                        headers={"Range": f"bytes={big_file_local_size_list[i]}-"},
                    ) as response:
                        if response.status_code == 404:
                            logging.info(f"Download complete: {file_url}")
                            break
                        if response.status_code not in [200, 206]:
                            logging.warning(f"Error: HTTP {response.status_code}, retrying...")
                            time.sleep(2**retry_num)
                            continue
                        start_time = time.time()
                        for n, chunk in enumerate(response.iter_content(chunk_size=1024)):
                            if chunk:
                                file_buffer.write(chunk)
                            if file_buffer.tell() >= 1024 * 1024:
                                sub_time = time.time() - start_time
                                speed = file_buffer.tell() // (sub_time + 1e-7)
                                fp.write(file_buffer.getvalue())
                                file_buffer.seek(0)
                                file_buffer.truncate(0)

                                big_file_local_size_list[i] = fp.tell()
                                download_size = sum(big_file_local_size_list)
                                total_size = sum(big_file_size_list)
                                download_progress = 100 * download_size // total_size if total_size > 0 else 0

                                ok = ModelService.update_model_status(
                                    model.model_name,
                                    DownloadStatus.DOWNLOADING,
                                    reset=True,
                                    download_progress=download_progress,
                                    download_speed=speed,
                                    process_message=translation_loader.translation.t(
                                        "model.download_info.download_size",
                                        cur_size=download_size // (1024 * 1024),
                                        total_size=total_size // (1024 * 1024),
                                    ),
                                )
                                logging.info(
                                    f"downloading {model.model_name}: {download_size}/{total_size}, speed: {speed}"
                                )
                                start_time = time.time()

                                if not ok:
                                    logging.info("Model download interrupted.")
                                    return

                        if file_buffer.tell() > 0:
                            fp.write(file_buffer.getvalue())
                            file_buffer.seek(0)
                            file_buffer.truncate(0)
                            big_file_local_size_list[i] = fp.tell()
                            download_size = sum(big_file_local_size_list)
                            total_size = sum(big_file_size_list)
                            ok = ModelService.update_model_status(
                                model.model_name,
                                DownloadStatus.DOWNLOADING,
                                reset=True,
                                download_progress=download_progress,
                                download_speed=speed,
                                process_message=translation_loader.translation.t(
                                    "model.download_info.download_size",
                                    cur_size=download_size // (1024 * 1024),
                                    total_size=total_size // (1024 * 1024),
                                ),
                            )
                            if not ok:
                                logging.info("Model download interrupted.")
                                return
                        logging.info(f"Download complete: {file_url}")
                        return
                except Exception as ex:
                    logging.warning(f"Retry {retry_num + 1}/{max_retries}, error: {ex}")
                    time.sleep(2**retry_num)
                    continue

    ModelService.update_model_status(
        model.model_name,
        DownloadStatus.DOWNLOAD_COMPLETE,
        download_progress=100,
        download_speed=0,
        process_message=translation_loader.translation.t("model.download_info.download_complete"),
    )
    logging.info(f"download {model.model_name} all success")


@register_id
def process_downloading_model(model: Model):
    try:
        get_site_latency()
        if ":" not in model.source:
            process_downloading_model_huggingface(model)
        elif ":" in model.source:
            process_downloading_model_ollama(model)
    except Exception as e:
        logging.exception(f"download {model.model_name} error")
        ModelService.update_model_status(
            model.model_name,
            DownloadStatus.DOWNLOAD_FAILED,
            process_message=translation_loader.translation.t("model.service_connection_failed"),
        )


@register_id
def process_convert_model(model: Model):
    model_name = model.model_name
    source_split = model.source.split("/")
    repo_id, gguf_file = "/".join(source_split[0:2]), None
    if len(source_split) == 3:
        gguf_file = source_split[2]

    try:
        if not gguf_file:
            # quantization_level = model.quantization_level or "f16"
            # convert(os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id), quantization_level)
            raise NotImplementedError("safetensors model is not supported, please use gguf model file")
        ModelService.update_model_status(model.model_name, DownloadStatus.CONVERT_COMPLETE)
    except Exception as e:
        logging.exception(f"convert model {model_name} failed.")
        ModelService.update_model_status(
            model.model_name,
            DownloadStatus.CONVERT_FAILED,
            process_message=translation_loader.translation.t("model.convert_gguf_fail"),
        )


def import_ollama_model(model: Model):
    ollama_model_name = model.ollama_model_name.removesuffix(":latest")
    source_split = model.source.split("/")
    repo_id, gguf_file = "/".join(source_split[0:2]), None
    if len(source_split) == 3:
        gguf_file = source_split[2]

    if not gguf_file:
        gguf_file = f"ggml-model-{model.quantization_level}.gguf"

    model_file = os.path.join(ARGO_STORAGE_PATH_TEMP_MODEL, repo_id, gguf_file)

    if USE_ARGO_OLLAMA != "true" and EXTERNAL_ARGO_PATH:
        logging.info(f"replace external argo path: {EXTERNAL_ARGO_PATH}")
        model_file = os.path.join(EXTERNAL_ARGO_PATH, "tmp_models", repo_id, gguf_file)

    llm = Llama(model_path=model_file, vocab_only=True, verbose=False)
    chat_template = llm.get_chat_template()
    if not chat_template:
        logging.warning(f"No chat_template found for model: {model.ollama_model_name}")

    result = None
    if chat_template:
        result = convert_gguf_template_to_ollama(
            {
                "chat_template": chat_template,
                "eos_token": llm.get_eos_token(),
                "bos_token": llm.get_bos_token(),
            }
        )
        if result is None:
            logging.warning(f"Failed to convert chat_template for model: {model.ollama_model_name}")

    ollama_template = None
    ollama_parameters = None
    if result:
        ollama_template = cast(Optional[str], result.ollama.get("template"))
        ollama_parameters = cast(Optional[dict], result.ollama.get("params"))

    try:
        provider_st = get_provider_setting(OLLAMA_PROVIDER)
        if not provider_st:
            raise ValueError(f"Provider '{OLLAMA_PROVIDER}' is not initialized")

        model_path = Path(model_file).expanduser()
        blob_digest = upload_model_blob(provider_st.safe_base_url, model_path)
        if not blob_digest:
            raise ValueError(f"Failed to upload blob for model file: {model_path}")

        return ollama_create_model(
            base_url=provider_st.safe_base_url,
            model_name=ollama_model_name,
            files={model_path.name: blob_digest},
            template=ollama_template,
            parameters=ollama_parameters,
        )

    except Exception as e:
        logging.exception(f"Failed to create Ollama model from file: {model_file}")
        msg = translation_loader.translation.t("model.ollama_create_fail")
        assert isinstance(msg, str)
        return msg


def upload_model_blob(base_url: str, file_path: Path) -> Optional[str]:
    try:
        if not file_path.exists():
            raise FileNotFoundError(f"Model file not found: {file_path}")

        file_bytes = file_path.read_bytes()
        blob_digest = hashlib.sha256(file_bytes).hexdigest()
        blob_ref = f"sha256:{blob_digest}"

        ollama_create_blob(base_url, blob_ref, file_path)
        return blob_ref

    except Exception as e:
        logging.exception(f"Failed to upload model blob from file: {file_path}")
        return None


@register_id
def process_import_model(model: Model):
    msg = import_ollama_model(model)
    if msg == "success":
        ModelService.update_model_status(model.model_name, DownloadStatus.IMPORT_COMPLETE)
    else:
        ModelService.update_model_status(model.model_name, DownloadStatus.IMPORT_FAILED, process_message=msg)


def test_response_time(url):
    try:
        start_time = time.time()
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        end_time = time.time()
        response_time = end_time - start_time
        return url, response_time
    except Exception as ex:
        return url, None


def get_site_latency():
    global site_info
    temp_site_info = {
        "https://huggingface.co/models": 999,
        "https://hf-mirror.com/models": 999,
        "https://modelscope.cn/models": 999,
    }

    with ThreadPoolExecutor(max_workers=len(site_info)) as executor:
        results = list(executor.map(test_response_time, site_info.keys()))

    valid_results = {url: cost for url, cost in results if cost is not None}

    if not valid_results:
        logging.error("all sites request timeout!")
        return

    temp_site_info.update(valid_results)
    with latency_lock:
        site_info = dict(sorted(temp_site_info.items(), key=operator.itemgetter(1)))

    msg_list = ["latency information: "]
    for url, latency in site_info.items():
        msg_list.append(f"url: {url}, latency: {'unreachable' if latency == 999 else latency}")
    logging.info("\n".join(msg_list))


def get_file_url(file_url, scope_flag) -> str:
    site_list = list(site_info.items())
    if site_list[0][0] == "https://modelscope.cn/models":
        if scope_flag:
            file_url = (
                file_url.replace("hf-mirror.com", "modelscope.cn/models")
                .replace("huggingface.co", "modelscope.cn/models")
                .replace("/main/", "/master/")
            )
        else:
            if site_list[1][0] == "https://hf-mirror.com/models":
                file_url = file_url.replace("huggingface.co", "hf-mirror.com")
            else:
                file_url = file_url.replace("hf-mirror.com", "huggingface.co")
    elif site_list[0][0] == "https://hf-mirror.com/models":
        file_url = file_url.replace("huggingface.co", "hf-mirror.com")
    else:
        file_url = file_url.replace("hf-mirror.com", "huggingface.co")
    return str(file_url)
