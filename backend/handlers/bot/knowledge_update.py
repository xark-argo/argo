import tornado.web

from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from schemas.bot import UpdateKnowledgeSchema
from services.doc.doc_db import DocDB
from services.doc.milvus_op import DocCollectionOp


class KnowledgeUpdateHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["bot_id", "collection_name", "embedding_model"]

    @RequestHandlerMixin.handle_request(UpdateKnowledgeSchema)
    def post(self):
        """
        ---
        tags: [Doc]
        summary: Update knowledge model information
        description: Update knowledge model information for a specific bot.

        requestBody:
            description: Update bot knowledge data
            required: True
            content:
                application/json:
                    schema:
                        UpdateKnowledgeSchema

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                      type: object
                      properties:
                        status:
                          type: boolean

          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """
        body = tornado.escape.json_decode(self.request.body)

        bot_id = body.get("bot_id", "")
        collection_name = body.get("collection_name", [])
        embedding_model = body.get("embedding_model", [])

        for each_collection_name, each_embedding_model in zip(collection_name, embedding_model):
            collection_info = DocCollectionOp.show_collection_info(collection_name=each_collection_name)
            if not collection_info or isinstance(collection_info, dict):
                continue
            if each_embedding_model != collection_info.get("embedding_model"):
                DocCollectionOp.update_collection(
                    collection_name=each_collection_name,
                    knowledge_name=collection_info.get("knowledge_name"),
                    description=collection_info.get("description"),
                    provider=collection_info.get("provider"),
                    embedding_model=each_embedding_model,
                    similarity_threshold=collection_info.get("similarity_threshold", 0.65),
                    dimension=collection_info.get("dimension", 128),
                    chunk_size=collection_info.get("chunk_size", 500),
                    chunk_overlap=collection_info.get("chunk_overlap", 50),
                    top_k=collection_info.get("top_k", 5),
                    folder=collection_info.get("folder", ""),
                )
                DocDB.update_model_by_bot_id(
                    bot_id=bot_id,
                    collection_name=each_collection_name,
                    embedding_model=each_embedding_model,
                )
        return {"status": True}


api_router.add("/api/bot/knowledge/update", KnowledgeUpdateHandler)
