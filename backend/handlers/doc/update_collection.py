import json
import logging
import os
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import tornado.web
from tornado.concurrent import run_on_executor

from configs.env import FOLDER_TREE_FILE
from configs.settings import FILE_SETTINGS
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers import model_provider_manager
from database import db
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.bot import BotModelConfig, get_bot
from services.common.provider_setting_service import get_provider_setting
from services.doc import util
from services.doc.doc_db import DocDB
from services.doc.milvus_op import DocCollectionOp


class UpdateCollectionHandler(BaseProtectedHandler):
    executor = ThreadPoolExecutor(max_workers=10)

    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = [
            "collection_name",
            "knowledge_name",
            "description",
            "embedding_model",
        ]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    @run_on_executor
    def post(self):
        """
        ---
        tags:
          - Doc
        summary: update knowledge base
        description: update knowledge info
        parameters:
          - in: body
            name: body
            description: update fields
            required: true
            schema:
              type: object
              required:
                - collection_name
                - knowledge_name
                - description
                - embedding_model
                - similarity_threshold
                - chunk_size
                - chunk_overlap
                - top_k
              properties:
                collection_name:
                  type: string
                knowledge_name:
                  type: string
                description:
                  type: string
                embedding_model:
                  type: string
                provider:
                  type: string
                similarity_threshold:
                  type: float
                chunk_size:
                  type: int
                chunk_overlap:
                  type: int
                top_k:
                  type: int
        responses:
          '200':
            description: knowledge update successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    status:
                      type: boolean
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

        collection_name = body.get("collection_name")
        provider = body.get("provider", "")
        knowledge_name = body.get("knowledge_name")
        description = body.get("description", "")
        embedding_model = body.get("embedding_model", "")
        similarity_threshold = body.get("similarity_threshold", 0.0)
        chunk_size = body.get("chunk_size", FILE_SETTINGS["CHUNK_SIZE"])
        chunk_overlap = body.get("chunk_overlap", FILE_SETTINGS["CHUNK_OVERLAP"])
        top_k = body.get("top_k", FILE_SETTINGS["TOP_K"])
        folder = body.get("folder", "")

        if not provider:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": "provider not exist",
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

        providerSt = get_provider_setting(provider)
        if not providerSt:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("provider.provider_not_exist"),
                }
            )
            return

        try:
            embedding = model_provider_manager.get_embedding_instance(provider, embedding_model)
            embeddings = embedding.embed_query("test")
            dimension = len(embeddings)
        except Exception as e:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("model.model_not_support_vector"),
                }
            )
            return

        if folder and not os.path.exists(folder):
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": f"{folder} is not a valid folder",
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
            success = DocCollectionOp.update_collection(
                collection_name=collection_name,
                knowledge_name=knowledge_name,
                description=description,
                provider=provider,
                embedding_model=embedding_model,
                similarity_threshold=similarity_threshold,
                dimension=dimension,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                top_k=top_k,
                folder=folder,
            )
            if success:
                datasets = DocDB.get_spaces_by_collection_name(collection_name=collection_name)
                for dataset in datasets:
                    bot = get_bot(dataset.bot_id)
                    with db.session_scope() as session:
                        model_config = session.query(BotModelConfig).get(bot.bot_model_config_id)
                        if model_config is None:
                            continue

                        agent_mode = json.loads(model_config.agent_mode)
                        tools = agent_mode["tools"]
                        for i in range(len(tools)):
                            cur_tool = tools[i]
                            if cur_tool["id"] == dataset.collection_name:
                                cur_tool["name"] = knowledge_name
                                cur_tool["description"] = description
                            tools[i] = cur_tool
                        agent_mode["tools"] = tools
                        model_config.agent_mode = json.dumps(agent_mode)
                        session.commit()
            if success:
                self.write(
                    {
                        "status": True,
                    }
                )
            else:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrCreateCollectionFail.value,
                        "msg": translation_loader.translation.t("doc.knowledge_not_change"),
                    }
                )
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write({"errcode": Errcode.ErrCreateCollectionFail.value, "msg": str(ex)})


api_router.add("/api/knowledge/update_knowledge_base", UpdateCollectionHandler)
