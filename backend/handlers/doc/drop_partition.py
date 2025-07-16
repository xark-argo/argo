import logging
from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.doc.milvus_op import DocCollectionOp


class DropPartitionHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["collection_name", "partition_name"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: drop vector partition
        description: drop partition
        parameters:
          - in: body
            name: body
            description: drop partition
            required: true
            schema:
              type: object
              required:
                - collection_name
                - partition_name
              properties:
                collection_name:
                  type: string
                partition_name:
                  type: string
        responses:
          '200':
            description: drop partition successfully
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
        partition_name = body.get("partition_name", None)
        if not collection_name or not partition_name:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrRemoveDocumentFail.value,
                    "msg": translation_loader.translation.t("doc.collection_name_or_partition_name_not_given"),
                }
            )
            return

        try:
            success = DocCollectionOp.drop_partition(collection_name=collection_name, partition_name=partition_name)
            if success:
                self.write({"status": True})
            else:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrRemoveDocumentFail.value,
                        "msg": translation_loader.translation.t(
                            "doc.remove_collection_partition_fail",
                            collection_name=collection_name,
                            partition_name=partition_name,
                        ),
                    }
                )
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrRemoveDocumentFail.value,
                    "msg": translation_loader.translation.t("doc.remove_document_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/drop_document", DropPartitionHandler)
