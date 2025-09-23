import os

from configs.env import ARGO_STORAGE_PATH_SQLITE

# Database configuration
DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "argo")
DB_USER = os.getenv("DB_USER", "argo")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Build database URL based on DB_TYPE
if DB_TYPE == "mysql":
    db_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
elif DB_TYPE == "sqlite":
    db_url = f"sqlite:///{ARGO_STORAGE_PATH_SQLITE}/sqlite.db"
else:
    # Fallback to custom DATABASE_URL if provided
    db_url = os.getenv("DATABASE_URL", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4")

DB_SETTINGS = {
    "db_url": db_url,
    "db_type": DB_TYPE,
    "db_host": DB_HOST,
    "db_port": int(DB_PORT),
    "db_name": DB_NAME,
    "db_user": DB_USER,
    "db_password": DB_PASSWORD,
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
