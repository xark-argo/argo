import json
import logging
import os.path
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import tornado.web
from tornado.concurrent import run_on_executor

from configs.env import FOLDER_TREE_FILE, MILVUS_DISTANCE_METHOD
from configs.settings import FILE_SETTINGS
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_model_exist
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.common.provider_setting_service import get_provider_setting
from services.doc import util
from services.doc.milvus_op import DocCollectionOp


class CreateCollectionHandler(BaseProtectedHandler):
    executor = ThreadPoolExecutor(max_workers=10)

    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["knowledge_name", "description", "embedding_model"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    @run_on_executor
    def post(self):
        """
        ---
        tags:
          - Doc
        summary: create knowledge base
        description: create knowledge
        parameters:
          - in: body
            name: body
            description: knowledge fields
            required: true
            schema:
              type: object
              required:
                - knowledge_name
                - description
                - embedding_model
              properties:
                knowledge_name:
                  type: string
                description:
                  type: string
                provider:
                  type: string
                embedding_model:
                  type: string
                index_type:
                  type: string
                metric_type:
                  type: string
                params:
                  type: object
        responses:
          '200':
            description: knowledge create successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    status:
                      type: boolean
                    collection_name:
                      type: string
          '500':
            description: Invalid input
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    errcode:
                      type: integer
                    msg:
                      type: string
        """
        body = tornado.escape.json_decode(self.request.body)

        knowledge_name = body.get("knowledge_name")
        description = body.get("description", "")
        provider = body.get("provider", "")
        embedding_model = body.get("embedding_model")
        similarity_threshold = body.get("similarity_threshold", 0.0)

        if not provider:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("provider.provider_not_exist"),
                }
            )
            return

        chunk_size = body.get("chunk_size", FILE_SETTINGS["CHUNK_SIZE"])
        chunk_overlap = body.get("chunk_overlap", FILE_SETTINGS["CHUNK_OVERLAP"])
        top_k = body.get("top_k", FILE_SETTINGS["TOP_K"])

        if provider == OLLAMA_PROVIDER:
            provider_st = get_provider_setting(OLLAMA_PROVIDER)
            if not provider_st:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeRequestNotFound.value,
                        "msg": translation_loader.translation.t(
                            "provider.provider_not_found",
                            provider=OLLAMA_PROVIDER,
                        ),
                    }
                )
                return

            if not ollama_model_exist(provider_st.safe_base_url, embedding_model):
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrCreateCollectionFail.value,
                        "msg": translation_loader.translation.t("model.embedding_model_not_exist"),
                    }
                )
                return

        if chunk_overlap > chunk_size:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("doc.chunk_overlap_invalid"),
                }
            )
            return

        index_type = body.get("index_type", "HNSW")
        metric_type = body.get("metric_type", MILVUS_DISTANCE_METHOD)
        params = body.get("params", {"M": 64, "efConstruction": 512})
        folder = body.get("folder", "")
        user_id = self.current_user.id

        if folder and not os.path.exists(folder):
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("file.folder_invalid", folder=folder),
                }
            )
            return

        if folder:
            local_file_map = util.get_file_list(folder)
            file_path = Path(folder) / FOLDER_TREE_FILE
            file_path.write_text(
                json.dumps(local_file_map, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            file_mod_time = os.path.getmtime(f"{folder}/{FOLDER_TREE_FILE}")
            os.utime(folder, (file_mod_time, file_mod_time + 5))

        try:
            result = DocCollectionOp.create_collection(
                user_id=user_id,
                knowledge_name=knowledge_name,
                description=description,
                provider=provider,
                embedding_model=embedding_model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                top_k=top_k,
                folder=folder,
                similarity_threshold=similarity_threshold,
                index_type=index_type,
                metric_type=metric_type,
                params=params,
            )
            if result["success"]:
                self.write({"status": True, "collection_name": result["collection_name"]})
            else:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrCreateCollectionFail.value,
                        "msg": translation_loader.translation.t("doc.create_knowledge_fail", ex=result["msg"]),
                    }
                )
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("doc.create_knowledge_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/create_knowledge_base", CreateCollectionHandler)
