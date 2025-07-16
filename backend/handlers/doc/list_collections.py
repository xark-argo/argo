from collections.abc import Awaitable
from typing import Optional

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.document import DOCUMENTSTATUS
from services.doc.milvus_op import DocCollectionOp


class ListCollectionsHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def get(self):
        """
        ---
        tags:
          - Doc
        summary: Get all collections
        responses:
          200:
            description: A map of collection to corresponding partition info
            schema:
              type: object
              properties:
                collection_info:
                  type: array
                  items:
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
        try:
            user_id = self.current_user.id
            collection_info = DocCollectionOp.list_collections_by_user_id(user_id=user_id)
            collection_info = [
                each for each in collection_info if each["knowledge_status"] != DOCUMENTSTATUS.READY.value
            ]
            self.write({"collection_info": collection_info})
        except Exception as ex:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("doc.get_knowledge_list_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/list_collections", ListCollectionsHandler)
