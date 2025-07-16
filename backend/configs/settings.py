import os

from configs.env import ARGO_STORAGE_PATH_SQLITE

DB_SETTINGS = {
    "db_url": os.getenv("DATABASE_URL", f"sqlite:///{ARGO_STORAGE_PATH_SQLITE}/sqlite.db"),
}

AUTH_SETTINGS = {
    "jwt_secret": "your_jwt_secret_key",
    "jwt_algorithm": "HS256",
}

APP_SETTINGS = {
    "debug": False,
}

FILE_SETTINGS = {
    "PDF_EXTRACT_IMAGES": True,
    "CHUNK_SIZE": 500,
    "CHUNK_OVERLAP": 50,
    "TOP_K": 5,
}

MODEL_PROVIDER_SETTINGS = {
    "ollama": {"base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")},
}


USE_LOCAL_OLLAMA = (
    True
    if "localhost" in MODEL_PROVIDER_SETTINGS["ollama"]["base_url"]
    or "127.0.0.1" in MODEL_PROVIDER_SETTINGS["ollama"]["base_url"]
    else False
)

VECTOR_SETTINTS = {
    "QDRANT_URI": os.getenv("QDRANT_URI", "http://localhost:6333"),
}
