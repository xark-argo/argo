import logging
from collections.abc import Awaitable
from typing import Optional

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.doc.doc_db import CollectionDB


class CreateTempCollectionHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: create temp knowledge base
        description: create temp knowledge
        parameters:
          - in: body
            name: body
            description: knowledge fields
            required: true
            schema:
              type: object
        responses:
          '200':
            description: knowledge create successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    status:
                      type: boolean
                    collection_name:
                      type: string
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
        # only create once
        db_collection = CollectionDB.get_collection_by_name(collection_name="temp")
        if db_collection:
            self.write(
                {
                    "status": True,
                }
            )
            return

        # index_params = {
        #     "index_type": 'HNSW',
        #     "metric_type": MILVUS_DISTANCE_METHOD,
        #     "params": {
        #         'M': 64,
        #         'efConstruction': 512
        #     }
        # }
        #
        # illegal = True
        # ollama_models = ollama_get_model_list().models
        # dimension = 768
        # embedding_model = ""
        # for each_model in ollama_models:
        #     try:
        #         embeddings = ollama_get_embeddings(each_model.name, "test")
        #         embedding_model = each_model.name
        #         dimension = len(embeddings.embedding)
        #         illegal = False
        #         break
        #     except Exception as ex:
        #         pass
        #
        # if illegal:
        #     self.set_status(500)
        #     self.write({
        #         "errcode": Errcode.ErrCreateCollectionFail.value,
        #         "msg": "no valid embedding model"
        #     })
        #     return

        user_id = self.current_user.id
        try:
            # db_collection = CollectionDB.get_collection_by_name(collection_name="temp")
            # if db_collection is None or embedding_model != db_collection.embedding_model:
            #     if db_collection is not None:
            #         DocCollectionOp.drop_collection(collection_name="temp")
            #     CollectionDB.store_tmp_collection_info(
            #         user_id=user_id,
            #         knowledge_name="temp",
            #         description="temp",
            #         embedding_model=embedding_model,
            #         index_params=index_params
            #     )
            #
            # fields = [
            #     FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            #     FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            #     FieldSchema(name="page_content", dtype=DataType.VARCHAR, max_length=8192),
            #     FieldSchema(name="metadata", dtype=DataType.JSON)
            # ]
            # schema = CollectionSchema(fields, description="dialogue knowledge")
            # collection = Collection(name="temp", schema=schema)
            # collection.create_index(field_name="vector", index_params=index_params)
            CollectionDB.store_tmp_collection_info(
                user_id=user_id,
                knowledge_name="temp",
                description="temp",
                embedding_model="",
                index_params={},
            )
            self.write(
                {
                    "status": True,
                }
            )
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreateCollectionFail.value,
                    "msg": translation_loader.translation.t("doc.create_temp_knowledge_fail", ex=str(ex)),
                }
            )


api_router.add("/api/knowledge/create_temp_knowledge_base", CreateTempCollectionHandler)
