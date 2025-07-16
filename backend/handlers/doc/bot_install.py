import json
import logging
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import tornado.web
from tornado.concurrent import run_on_executor

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_check_addr, ollama_model_exist
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.bot import get_bot, get_model_config
from models.document import DOCUMENTSTATUS
from models.model_manager import DownloadStatus
from services.common.provider_setting_service import get_provider_setting
from services.doc.doc_db import CollectionDB, DocDB, PartitionDB
from services.model.model_service import ModelService


class BotInstallHandler(BaseProtectedHandler):
    executor = ThreadPoolExecutor(max_workers=10)

    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["bot_id"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    @run_on_executor
    def post(self):
        """
        ---
        tags:
          - Doc
        summary: bot install
        description: bot install, include chat model, embedding model and knowledge base
        parameters:
          - in: body
            name: body
            description: bot id
            required: true
            schema:
              type: object
              required:
                - bot_id
              properties:
                bot_id:
                  type: string
        responses:
          '200':
            description: bot install ready
            schema:
              type: object
              properties:
                status:
                  type: boolean
              example:
                status: true
          '500':
            description: Invalid input
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
              example:
                errcode: 400
                msg: "Invalid bot ID"
        """
        body = tornado.escape.json_decode(self.request.body)

        bot_id = body.get("bot_id", "")
        if not bot_id:
            self.set_status(500)
            self.write({"errcode": Errcode.ErrBotInstallFail.value, "msg": "lack of bot id"})
            return

        try:
            bot = get_bot(bot_id)
            if bot:
                model_config = get_model_config(bot.bot_model_config_id)
                if model_config:
                    model_json = json.loads(model_config.model)
                    chat_model_name = model_json["name"]
                    provider_name = model_json.get("provider", OLLAMA_PROVIDER)
                    provider_st = get_provider_setting(provider_name)
                    if not provider_st:
                        raise ValueError(f"Please set provider for {provider_name}")

                    model_info = ModelService.get_model_info(chat_model_name)
                    if model_info and provider_name == OLLAMA_PROVIDER:
                        if ollama_check_addr(provider_st.safe_base_url):
                            self.set_status(500)
                            self.write(
                                {
                                    "errcode": Errcode.ErrBotInstallFail.value,
                                    "msg": translation_loader.translation.t("model.ollama_service_unavailable"),
                                }
                            )
                            return
                        if ollama_model_exist(provider_st.safe_base_url, model_info.ollama_model_name):
                            ModelService.update_model_status(
                                model_name=chat_model_name,
                                download_status=DownloadStatus.ALL_COMPLETE,
                            )
                        else:
                            ModelService.update_model_status(
                                model_name=chat_model_name,
                                download_status=DownloadStatus.DOWNLOAD_WAITING,
                            )

            datasets = DocDB.get_datasets_by_bot_id(bot_id=bot_id)
            for each_dataset in datasets:
                collection_name = each_dataset.collection_name
                knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
                if knowledge is None:
                    continue

                # 先判断provider存在 再更新知识库状态
                if knowledge.provider and knowledge.provider != OLLAMA_PROVIDER:
                    provider_st = get_provider_setting(knowledge.provider)
                    if not provider_st:
                        raise ValueError(f"Please set provider for {knowledge.provider}")
                else:
                    provider_st = get_provider_setting(OLLAMA_PROVIDER)
                    if not provider_st:
                        raise ValueError(f"Please set provider for {knowledge.provider}")
                    if ollama_check_addr(provider_st.safe_base_url):
                        self.set_status(500)
                        self.write(
                            {
                                "errcode": Errcode.ErrBotInstallFail.value,
                                "msg": translation_loader.translation.t("model.ollama_service_unavailable"),
                            }
                        )
                        return
                    if ollama_model_exist(provider_st.safe_base_url, knowledge.embedding_model):
                        ModelService.update_model_status(
                            model_name=knowledge.embedding_model,
                            download_status=DownloadStatus.ALL_COMPLETE,
                        )
                    else:
                        ModelService.update_model_status(
                            model_name=knowledge.embedding_model,
                            download_status=DownloadStatus.DOWNLOAD_WAITING,
                        )

                # 再更新知识库状态
                if knowledge.knowledge_status != DOCUMENTSTATUS.FINISH.value:
                    CollectionDB.update_collection_status(
                        collection_name=collection_name,
                        status=DOCUMENTSTATUS.WAITING.value,
                    )
                    documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
                    for document in documents:
                        PartitionDB.update_status(
                            partition_name=document.partition_name,
                            status=DOCUMENTSTATUS.WAITING.value,
                        )
            self.write({"status": True})
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrBotInstallFail.value,
                    "msg": translation_loader.translation.t("bot.bot_install_fail", ex=str(ex)),
                }
            )


api_router.add(r"/api/bot/install_bot", BotInstallHandler)
