import logging
from collections.abc import Awaitable
from typing import Optional, Union, cast

import tornado

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.document import DOCUMENTSTATUS
from services.doc.milvus_op import DocCollectionOp


class ListDocumentsHandler(BaseProtectedHandler):
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
        summary: Get document list and collection info by collection name
        description: Get collection detail by its collection name
        parameters:
          - in: body
            name: body
            description: collection name
            required: true
            schema:
              type: object
              required:
                - collection_name
              properties:
                collection_name:
                  type: string
                partition_names:
                  type: array
                  items:
                    type: string
        responses:
          200:
            description: Collection details
            schema:
              type: object
              additionalProperties:
                type: object
                additionalProperties:
                  type: object
                  properties:
                    knowledge_name:
                      type: string
                      description: Knowledge name
                    collection_name:
                      type: string
                      description: Unique collection name
                    description:
                      type: string
                      description: Collection description
                    provider:
                      type: string
                      description: Provider of the embedding_model
                    embedding_model:
                      type: string
                      description: Embedding model to encode text to vector
                    index_params:
                      type: object
                      description: Vector search index parameters
                    create_at:
                      type: integer
                      description: Collection creation timestamp
                    update_at:
                      type: integer
                      description: Collection update timestamp
                    chunk_size:
                      type: integer
                      description: Knowledge chunk size
                    chunk_overlap:
                      type: integer
                      description: Knowledge chunk overlap
                    top_k:
                      type: integer
                      description: Knowledge result top_k
                    partition_info:
                      type: array
                      items:
                        type: object
                        properties:
                          partition_name:
                            type: string
                            description: Unique partition name
                          document_name:
                            type: string
                            description: The document name given by user
                          document_url:
                            type: string
                            description: The document server url
                          file_type:
                            type: string
                            description: Document file type
                          description:
                            type: string
                            description: Description for the document
                          progress:
                            type: float
                            description: document process progress
                          document_status:
                            type: int
                            description: document status, waiting is 1, fail is 2, finish is 3
                          msg:
                            type: string
                            description: if document upload fail, given the fail reason
                          create_at:
                            type: integer
                            description: Document create timestamp
                          update_at:
                            type: integer
                            description: Document update timestamp
                      description: Document info list
          500:
            description: Invalid input
        """
        body = tornado.escape.json_decode(self.request.body)
        collection_name = body.get("collection_name", "")
        partition_names = body.get("partition_names", [])

        try:
            collection_info = DocCollectionOp.show_collection_info(collection_name=collection_name)
            partition_info_raw = collection_info.get("partition_info")
            if isinstance(partition_info_raw, list):
                partition_info = cast(list[dict[str, Union[str, float, int]]], partition_info_raw)

                filtered_partitions = [
                    part for part in partition_info if part.get("document_status") != DOCUMENTSTATUS.DELETE.value
                ]

                if partition_names:
                    filtered_partitions = [
                        part for part in filtered_partitions if part.get("partition_name") in partition_names
                    ]

                collection_info["partition_info"] = filtered_partitions

            self.write(collection_info)
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrShowDocumentFail.value,
                    "msg": translation_loader.translation.t("doc.get_document_list_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/list_documents", ListDocumentsHandler)
