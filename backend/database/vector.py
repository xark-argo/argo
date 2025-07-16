from typing import Optional

from qdrant_client import QdrantClient

from core.third_party.qdrant import default_server

VECTOR_CLIENT_QDRANT: Optional[QdrantClient] = None


def init():
    # qdrant = QdrantClient(default_server.uri)
    qdrant = QdrantClient(path=default_server.qdrant_dir)

    global VECTOR_CLIENT_QDRANT
    VECTOR_CLIENT_QDRANT = qdrant
    # logging.info(f"qdrant init ok, {default_server.uri}")


def get_qdrant_client():
    return VECTOR_CLIENT_QDRANT
