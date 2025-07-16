from collections.abc import Awaitable
from typing import Optional

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.doc.doc_db import DocDB


class ListDatasetsHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def get(self):
        """
        ---
        tags:
          - Doc
        summary: Get all datasets
        responses:
          '200':
            description: A list of dataset
            content:
              application/json:
                schema:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: string
                      space_id:
                        type: string
                      description:
                        type: string
                      permission:
                        type: integer
                      embedding_model:
                        type: string
                      collection_name:
                        type: string
                      partition_names:
                        type: array
                        items:
                          type: string
                      created_at:
                        type: integer
                      updated_at:
                        type: integer
                      user_id:
                        type: string
          '400':
            description: Invalid input
        """
        try:
            datasets = DocDB.get_all_datasets()
            dataset_list = [
                {
                    "id": str(dataset.id),
                    "space_id": str(dataset.space_id),
                    "description": dataset.description,
                    "permission": dataset.permission,
                    "embedding_model": dataset.embedding_model,
                    "collection_name": dataset.collection_name,
                    "partition_names": dataset.partition_names,
                    "created_at": int(dataset.created_at.timestamp()),
                    "updated_at": int(dataset.updated_at.timestamp()),
                    "user_id": str(dataset.user_id),
                }
                for dataset in datasets
            ]
            self.write({"dataset_list": dataset_list})
        except Exception as ex:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("doc.get_dataset_info_fail", ex=ex),
                }
            )


api_router.add("/api/knowledge/list_datasets", ListDatasetsHandler)
