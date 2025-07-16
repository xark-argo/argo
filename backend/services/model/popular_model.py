import logging
import re
import threading
import time

import psutil
import requests
from bs4 import BeautifulSoup

from core.entities.model_entities import APIModelCategory
from core.model_providers.model_category_style import get_model_style
from utils.size_utils import convert_bits

popular_model_cache = []


def init():
    threading.Thread(target=period_update_popular_model, daemon=True).start()


def period_update_popular_model():
    global popular_model_cache
    while True:
        popular_model = get_popular_model()
        if popular_model:
            popular_model_cache = popular_model
        time.sleep(86400)


def refresh_popular_model():
    global popular_model_cache
    popular_model = get_popular_model()
    if popular_model:
        popular_model_cache = popular_model


def get_cached_popular_model():
    return popular_model_cache


def parse_model_size(size_str: str) -> float:
    size_str = size_str.strip().lower()

    if size_str == "latest":
        return 0

    match = re.match(r"^(\d+)x(\d+)b$", size_str)
    if match:
        count = float(match.group(1))
        billion = float(match.group(2))
        return count * billion * 1024**3 / 2

    match = re.match(r"^e?(\d+(?:\.\d+)?)b$", size_str)
    if match:
        billion = float(match.group(1))
        return billion * 1024**3 / 2

    match = re.match(r"^(\d+(?:\.\d+)?)m$", size_str)
    if match:
        million = float(match.group(1))
        return million * 1024**2 * 2

    return 0


def get_popular_model():
    try:
        total = psutil.virtual_memory().total

        url = "https://ollama.com/library?sort=popular"
        html = requests.get(url).content.decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")

        ul = soup.find("div", id="repo")
        model_list = []
        name_dict = {}
        for li in ul.find_all("li"):
            model_name = li.find("h2").text.strip()
            if model_name in name_dict:
                continue
            desc = li.find("p", class_="text-md").text.strip()
            capabilities = [span.text.strip() for span in li.find_all("span", {"x-test-size": True})]
            cap_sizes = [parse_model_size(each) for each in capabilities]

            available = [
                {"parameter": size, "size": convert_bits(num_bytes)}
                for size, num_bytes in zip(capabilities, cap_sizes)
                if num_bytes * 1.2 <= total
            ]
            unavailable = [
                {"parameter": size, "size": convert_bits(num_bytes)}
                for size, num_bytes in zip(capabilities, cap_sizes)
                if num_bytes * 1.2 > total
            ]
            if len(capabilities) == 0:
                available = [{"parameter": "latest", "size": "Unknown"}]

            if len(available) > 0:
                select_size = available[-1]
            elif len(unavailable) > 0:
                select_size = unavailable[0]
            else:
                select_size = {}

            categories = [span.text.strip() for span in li.find_all("span", {"x-test-capability": True})]
            total_downloads = li.find("span", {"x-test-pull-count": True}).text.strip()
            updated_at = li.find("span", {"x-test-updated": True}).text.strip()
            name_dict[model_name] = True
            model_list.append(
                {
                    "model_name": model_name,
                    "desc": desc,
                    "available": available,
                    "unavailable": unavailable,
                    "select_size": select_size,
                    "category": {
                        "extra_label": [
                            each for each in categories if each not in [category.value for category in APIModelCategory]
                        ],
                        "category_label": {
                            "type": (
                                APIModelCategory.EMBEDDING.value
                                if APIModelCategory.EMBEDDING.value in categories
                                else APIModelCategory.CHAT.value
                            ),
                            "category": [
                                get_model_style(each)
                                for each in categories
                                if each
                                in [
                                    APIModelCategory.TOOLS.value,
                                    APIModelCategory.EMBEDDING.value,
                                    APIModelCategory.VISION.value,
                                ]
                            ],
                        },
                    },
                    "total_downloads": total_downloads,
                    "updated_at": updated_at,
                }
            )

            # temp patch
            if "milkey/dmeta-embedding-zh" not in name_dict:
                model_list.append(
                    {
                        "model_name": "milkey/dmeta-embedding-zh",
                        "desc": "Dmeta-embedding is a cross-domain, cross-task, \
                        out-of-the-box Chinese embedding model.",
                        "available": [{"parameter": "f16", "size": "205 MB"}],
                        "unavailable": [],
                        "select_size": {"parameter": "f16", "size": "205 MB"},
                        "category": {
                            "extra_label": [],
                            "category_label": {
                                "type": APIModelCategory.EMBEDDING.value,
                                "category": [get_model_style(APIModelCategory.EMBEDDING.value)],
                            },
                        },
                        "total_downloads": "1122",
                        "updated_at": "10 months ago",
                    }
                )
            name_dict["milkey/dmeta-embedding-zh"] = True
            if "shaw/dmeta-embedding-zh" not in name_dict:
                model_list.append(
                    {
                        "model_name": "shaw/dmeta-embedding-zh",
                        "desc": "https://huggingface.co/DMetaSoul/Dmeta-embedding-zh",
                        "available": [{"parameter": "latest", "size": "409 MB"}],
                        "unavailable": [],
                        "select_size": {"parameter": "latest", "size": "409 MB"},
                        "category": {
                            "extra_label": [],
                            "category_label": {
                                "type": APIModelCategory.EMBEDDING.value,
                                "category": [get_model_style(APIModelCategory.EMBEDDING.value)],
                            },
                        },
                        "total_downloads": "91.4K",
                        "updated_at": "10 months ago",
                    }
                )
            name_dict["shaw/dmeta-embedding-zh"] = True
            if "shaw/dmeta-embedding-zh-q4" not in name_dict:
                model_list.append(
                    {
                        "model_name": "shaw/dmeta-embedding-zh-q4",
                        "desc": "The Q4_K_M quantized version of dmeta-embedding-zh.",
                        "available": [{"parameter": "latest", "size": "70 MB"}],
                        "unavailable": [],
                        "select_size": {"parameter": "latest", "size": "70 MB"},
                        "category": {
                            "extra_label": [],
                            "category_label": {
                                "type": APIModelCategory.EMBEDDING.value,
                                "category": [get_model_style(APIModelCategory.EMBEDDING.value)],
                            },
                        },
                        "total_downloads": "342",
                        "updated_at": "10 months ago",
                    }
                )
            name_dict["shaw/dmeta-embedding-zh-q4"] = True
        return model_list
    except Exception as e:
        logging.exception("Error occurred while fetching or parsing popular models from Ollama.")
