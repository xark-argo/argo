import tornado

from core.i18n.translation import translation_loader
from handlers.base_handler import BaseRequestHandler
from handlers.router import api_router


class SetLanguageHandler(BaseRequestHandler):
    def post(self):
        """
        ---
        tags:
          - Workspace
        summary: set language
        description: set language
        parameters:
          - in: body
            name: body
            description: language fields
            required: true
            schema:
              type: object
              required:
                - language
              properties:
                language:
                  type: string
        responses:
          '200':
            description: shift language successfully
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
        language = body.get("language", "zh")
        translation_loader.translation.set_locale(language=language)
        self.set_status(200)
        self.write({"status": True})


api_router.add("/api/workspaces/set_language", SetLanguageHandler)
