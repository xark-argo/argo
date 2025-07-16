import logging
from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.bot.bot_service import BotService


class BotStatusQueryHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["bot_id"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: bot status get
        description: bot status get, include chat model, embedding model and knowledge base progress
        parameters:
          - in: body
            name: body
            description: bot id
            required: true
            schema:
              type: object
              required:
                - bot_id
              properties:
                bot_id:
                  type: string
        responses:
          200:
            description: bot status query
            schema:
              type: object
              properties:
                chat_model_info:
                  type: object
                  properties:
                    model_name:
                      type: string
                      description: chat model name
                    download_status:
                      type: string
                      description: download status
                    download_speed:
                      type: integer
                      description: download speed
                    download_progress:
                      type: integer
                      description: download progress, integer
                    process_message:
                      type: string
                      description: download model fail reason
                embedding_model_info_list:
                  type: array
                  items:
                    type: object
                    properties:
                      model_name:
                        type: string
                        description: embedding model name
                      download_status:
                        type: string
                        description: download status
                      download_speed:
                        type: integer
                        description: download speed
                      download_progress:
                        type: integer
                        description: download progress, integer
                      process_message:
                        type: string
                        description: embedding model fail reason
                      provider_status:
                        type: string
                        description: provider status
                        example: not_init | available
                      provider:
                        type: string
                        description: provider source
                knowledge_info_list:
                  type: array
                  items:
                    type: object
                    properties:
                      knowledge_name:
                        type: string
                        description: knowledge name
                      knowledge_progress:
                        type: float
                        description: knowledge progress, float
                      knowledge_status:
                        type: integer
                        description: knowledge status, waiting is 1, fail is 2, finish is 3
                      embedding_model:
                        type: string
                        description: knowledge's embedding model
                      collection_name:
                        type: string
                        description: knowledge collection name
              example:
                chat_model_info:
                  model_name: glm4:9b
                  download_status: downloading
                  download_speed: 10
                  download_progress: 70
                  process_message: "Error: /home/work/argo/glm:9b is not a directory"
                  provider_status: not_init
                  provider: "Provider openai not settings"
                embedding_model_info_list:
                  - model_name: shaw/dmeta-embedding-zh:latest
                    download_status: downloading
                    download_speed: 20
                    download_progress: 31
                    process_message: "Error: /home/work/argo/dmeta-embedding-zh:latest is not a directory"
                    provider_status: not_init
                    provider: "Provider openai not settings"
                knowledge_info_list:
                  - knowledge_name: abc
                    knowledge_progress: 0.25
                    knowledge_status: 1
          500:
            description: Invalid input
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: string
        """
        body = tornado.escape.json_decode(self.request.body)

        bot_id = body.get("bot_id", "")
        if not bot_id:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrBotInstallFail.value,
                    "msg": translation_loader.translation.t("bot.lack_of_bot_id"),
                }
            )
            return

        try:
            bot_detail = BotService.get_bot_detail(bot_id)
            self.write(bot_detail)
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrBotInstallFail.value,
                    "msg": translation_loader.translation.t("bot.bot_status_query_fail", ex=str(ex)),
                }
            )


api_router.add("/api/bot/bot_status_query", BotStatusQueryHandler)
