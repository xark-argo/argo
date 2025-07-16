import time

from core.errors.errcode import Errcode
from handlers.base_handler import BaseRequestHandler
from handlers.router import api_router


class HealthCheckHandler(BaseRequestHandler):
    def _log(self):
        return

    def get(self):
        """
        ---
        tags:
          - System
        summary: Health check
        description: |
          Health check endpoint. Can be accessed via GET or POST.
          Returns current server timestamp in both integer and formatted string formats.
        produces:
          - application/json
        responses:
          200:
            description: Health check response with current timestamp.
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                msg:
                  type: object
                  properties:
                    timestamp:
                      type: integer
                    timestamp-str:
                      type: string
        """
        self.post()

    def post(self):
        """
        ---
        tags:
          - System
        summary: Health check
        description: |
          Health check endpoint. Can be accessed via GET or POST.
          Returns current server timestamp in both integer and formatted string formats.
        produces:
          - application/json
        responses:
          200:
            description: Health check response with current timestamp.
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                  description: Status code, 0 means success.
                  example: 0
                msg:
                  type: object
                  properties:
                    timestamp:
                      type: integer
                      description: Current UNIX timestamp.
                      example: 1717660800
                    timestamp-str:
                      type: string
                      description: Human-readable timestamp.
                      example: "2025-06-06 20:00:00"
        """
        timestamp = int(time.time())
        self.write(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "msg": {
                    "timestamp": timestamp,
                    "timestamp-str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
                },
            }
        )


api_router.add("/healthcheck", HealthCheckHandler)
