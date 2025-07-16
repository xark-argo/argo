import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv

from utils.network import is_china_network

PROJECT_ROOT = Path(__file__).parent.parent

EXTERNAL_ARGO_PATH = os.getenv("EXTERNAL_ARGO_PATH", "")

ARGO_STORAGE_PATH = os.getenv("ARGO_STORAGE_PATH", os.path.join(os.path.expanduser("~"), ".argo"))
if not os.path.exists(ARGO_STORAGE_PATH):
    os.makedirs(ARGO_STORAGE_PATH)

FOLDER_TREE_FILE = ".folder_tree.json"

ENV_PATH = os.path.join(os.path.abspath("."), ".env")
# Check if running as a compiled app
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ENV_PATH = os.path.join(ARGO_STORAGE_PATH, ".env")

load_dotenv(ENV_PATH)

ARGO_STORAGE_PATH_SETTINGS = os.path.join(ARGO_STORAGE_PATH, "settings.db")

ARGO_STORAGE_PATH_TEMP_MODEL = os.path.join(ARGO_STORAGE_PATH, "tmp_models")
if not os.path.exists(ARGO_STORAGE_PATH_TEMP_MODEL):
    os.makedirs(ARGO_STORAGE_PATH_TEMP_MODEL)

ARGO_STORAGE_PATH_DOCUMENTS = os.path.join(ARGO_STORAGE_PATH, "local_documents")
if not os.path.exists(ARGO_STORAGE_PATH_DOCUMENTS):
    os.makedirs(ARGO_STORAGE_PATH_DOCUMENTS)

ARGO_STORAGE_PATH_MILVUS_LITE = os.path.join(ARGO_STORAGE_PATH, "milvus_lite")
if not os.path.exists(ARGO_STORAGE_PATH_MILVUS_LITE):
    os.makedirs(ARGO_STORAGE_PATH_MILVUS_LITE)

ARGO_STORAGE_PATH_SQLITE = os.path.join(ARGO_STORAGE_PATH, "sqlite")
if not os.path.exists(ARGO_STORAGE_PATH_SQLITE):
    os.makedirs(ARGO_STORAGE_PATH_SQLITE)

ARGO_STORAGE_PATH_DEPENDENCE_TOOL = os.path.join(ARGO_STORAGE_PATH, "dependences")
if not os.path.exists(ARGO_STORAGE_PATH_DEPENDENCE_TOOL):
    os.makedirs(ARGO_STORAGE_PATH_DEPENDENCE_TOOL)

IS_CHINA_NETWORK_ENV = is_china_network()

_HF_CHINA_ENDPOINT = "https://hf-mirror.com"
if os.getenv("HF_ENDPOINT") is None and IS_CHINA_NETWORK_ENV:
    os.environ["HF_ENDPOINT"] = _HF_CHINA_ENDPOINT


ARGO_STORAGE_PATH_TEMP_BOT = os.path.join(ARGO_STORAGE_PATH, "tmp_bot")
if not os.path.exists(ARGO_STORAGE_PATH_TEMP_BOT):
    os.makedirs(ARGO_STORAGE_PATH_TEMP_BOT)

USE_ARGO_OLLAMA = os.getenv("USE_ARGO_OLLAMA", "false")
ENABLE_MULTI_USER = os.getenv("ENABLE_MULTI_USER", "false")

os_name = platform.system()
MILVUS_DISTANCE_METHOD = "IP" if os_name == "Windows" else "COSINE"
