import logging
from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from models.dataset import PERMISSION
from services.doc.doc_db import CollectionDB, DocDB


class BindSpaceHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["space_id", "bot_id", "description", "collection_name"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    @RequestHandlerMixin.handle_request()
    def post(self):
        """
        ---
        tags: [Doc]
        summary: bind space
        description: bind space with knowledge collections
        parameters:
          - in: body
            name: body
            description: bind parameters
            required: true
            schema:
              type: object
              required:
                - space_id
                - bot_id
                - description
                - collection_name
              properties:
                space_id:
                  type: string
                bot_id:
                  type: string
                description:
                  type: string
                collection_name:
                  type: string
                permission:
                  type: integer
        responses:
          '200':
            description: bind space successfully
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

        user_id = self.current_user.id
        space_id = body.get("space_id", "")
        bot_id = body.get("bot_id", "")
        description = body.get("description", "")
        collection_name = body.get("collection_name")
        permission = body.get("permission", PERMISSION.ALL_USER.value)

        if not space_id:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrBindSpaceFail.value,
                    "msg": translation_loader.translation.t("doc.lack_of_space_id"),
                }
            )
            return

        try:
            knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
            if knowledge is None:
                raise Exception(f"collection {collection_name} not exists")
            embedding_model = knowledge.embedding_model
            DocDB.create_new_doc(
                space_id,
                bot_id,
                description,
                user_id,
                collection_name,
                embedding_model=embedding_model,
                permission=permission,
            )
            self.write({"status": True})
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrBindSpaceFail.value,
                    "msg": translation_loader.translation.t("doc.bind_knowledge_collections_fail", ex=ex),
                }
            )


api_router.add("/api/knowledge/bind_workspace", BindSpaceHandler)
