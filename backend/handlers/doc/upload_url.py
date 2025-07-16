import logging
import re
from collections.abc import Awaitable
from typing import Optional

import requests
import tornado
from bs4 import BeautifulSoup

from configs.env import ARGO_STORAGE_PATH_DOCUMENTS
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.doc.doc_db import CollectionDB, PartitionDB
from services.doc.util import random_ua
from services.file.file_op import upload_file


class UploadUrlHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: update url document
        description: create partition
        parameters:
          - in: body
            name: body
            description: url address
            required: true
            schema:
              type: object
              required:
                - collection_name
                - url
              properties:
                collection_name:
                  type: string
                url:
                  type: string
                name:
                  type: string
        responses:
          '200':
            description: create url partition successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    status:
                      type: boolean
                      description: url upload status
                    collection_name:
                      type: string
                      description: collection name
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
        url = body.get("url", "")
        file_name = body.get("name", "")

        knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
        if knowledge is None:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": translation_loader.translation.t(
                        "doc.knowledge_not_exists", collection_name=collection_name
                    ),
                }
            )
            return

        try:
            res = requests.get(url, headers={"User-Agent": random_ua()})
            if res.status_code // 100 != 2:
                self.set_status(500)
                self.write(
                    {
                        "errcode": Errcode.ErrCreatePartitionFail.value,
                        "msg": f"url {url} visit fail",
                    }
                )
                return
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": f"url {url} visit fail",
                }
            )
            return

        user_id = self.current_user.id
        soup = BeautifulSoup(res.content, "html.parser")
        page_content = soup.get_text()

        s = re.sub(r"\s+", "", page_content)
        if len(s) == 0:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": f"url {url} content empty",
                }
            )
            return

        if not file_name:
            file_name = f"{s[:5]}.txt"
        else:
            file_name = f"{file_name}.txt"
        result = upload_file(
            user_id=user_id,
            file_name=file_name,
            file_content=page_content.encode("utf-8"),
            folder=(knowledge.folder or ARGO_STORAGE_PATH_DOCUMENTS),
        )
        file_id = result["file_id"]
        file_size = result["file_size"]
        file_url = f"/api/documents/{file_id}"
        try:
            document_names = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
            file_ids = [document.file_id for document in document_names]
            if file_id in file_ids:
                raise Exception(f"duplicate file: {file_name}")
            PartitionDB.create_document(
                collection_name=collection_name,
                file_id=file_id,
                file_name=result["file_name"],
                file_url=file_url,
                file_size=file_size,
                file_type="txt",
                description=f"content from {url}",
                progress=0.0,
            )
            self.write({"status": True, "collection_name": collection_name})
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write({"errcode": Errcode.ErrCreatePartitionFail.value, "msg": str(ex)})


api_router.add("/api/knowledge/upload_url", UploadUrlHandler)
