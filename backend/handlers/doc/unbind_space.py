import logging
from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.doc.doc_db import DocDB


class UnBindSpaceHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["space_id", "bot_id", "collection_name"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: unbind space
        description: unbind space with knowledge collections
        parameters:
          - in: body
            name: body
            description: unbind parameters
            required: true
            schema:
              type: object
              required:
                - space_id
                - bot_id
                - collection_name
              properties:
                space_id:
                  type: string
                bot_id:
                  type: string
                collection_name:
                  type: string
        responses:
          '200':
            description: unbind space successfully
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

        space_id = body.get("space_id", "")
        bot_id = body.get("bot_id", "")
        collection_name = body.get("collection_name")

        if not space_id:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrUnBindSpaceFail.value,
                    "msg": translation_loader.translation.t("doc.lack_of_space_id"),
                }
            )
            return

        try:
            DocDB.delete_dataset(space_id=space_id, bot_id=bot_id, collection_name=collection_name)
            self.write({"status": True})
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrUnBindSpaceFail.value,
                    "msg": translation_loader.translation.t("doc.unbind_space_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/unbind_workspace", UnBindSpaceHandler)
