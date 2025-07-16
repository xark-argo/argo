import logging
from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from events.knowledge_event import knowledge_delete
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.bot import get_bot
from services.doc.doc_db import CollectionDB, DocDB
from services.doc.milvus_op import DocCollectionOp


class DropCollectionHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["collection_name"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: drop collection
        description: drop collection
        parameters:
          - in: body
            name: body
            description: drop collection name
            required: true
            schema:
              type: object
              required:
                - collection_name
              properties:
                collection_name:
                  type: string
                force:
                  type: bool
        responses:
          '200':
            description: drop collection successfully
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

        collection_name = body.get("collection_name", None)
        force = body.get("force", False)

        try:
            knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
            if not knowledge:
                self.write({"status": True})
                return

            if not force:
                datasets = DocDB.get_spaces_by_collection_name(collection_name=collection_name)
                if datasets:
                    bot_info = []
                    for dataset in datasets:
                        bot = get_bot(dataset.bot_id)
                        if translation_loader.translation.language == "en":
                            bot_info.append(f"bot_name: {bot.name}, description: {bot.description}")
                        else:
                            bot_info.append(f"机器人名称：{bot.name}，描述：{bot.description}")
                    self.set_status(500)
                    self.write(
                        {
                            "errcode": Errcode.ErrDropCollectionFail.value,
                            "msg": translation_loader.translation.t(
                                "doc.current_collection_quoted_by_bots",
                                bot_info=bot_info,
                            ),
                        }
                    )
                    return

            DocCollectionOp.drop_collection(collection_name=collection_name)
            knowledge_delete.send(collection_name, knowledge_name=knowledge.knowledge_name)
            self.write({"status": True})
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrDropCollectionFail.value,
                    "msg": translation_loader.translation.t("doc.drop_collection_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/drop_knowledge_base", DropCollectionHandler)
