from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.document import DOCUMENTSTATUS
from services.doc.doc_db import PartitionDB


class RestoreDocumentHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["partition_name"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: restore document
        description: restore document
        parameters:
          - in: body
            name: body
            description: restore document and analyse again
            required: true
            schema:
              type: object
              required:
                - partition_name
              properties:
                partition_name:
                  type: string
        responses:
          '200':
            description: document update successfully
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

        partition_name = body.get("partition_name")
        partition = PartitionDB.get_partition_by_partition_name(partition_name=partition_name)
        if partition is None:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrRemoveDocumentFail.value,
                    "msg": translation_loader.translation.t("doc.document_not_exists", partition_name=partition_name),
                }
            )
            return

        if partition.document_status == DOCUMENTSTATUS.DELETE.value:
            PartitionDB.update_status(
                partition_name=partition_name,
                status=DOCUMENTSTATUS.WAITING.value,
                msg="",
            )
            PartitionDB.update_progress(partition_name=partition_name, progress=0.0)
        self.write(
            {
                "status": True,
            }
        )


api_router.add("/api/knowledge/restore_document", RestoreDocumentHandler)
