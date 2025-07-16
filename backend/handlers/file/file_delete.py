from collections.abc import Awaitable
from typing import Optional

import tornado.web

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.file.file_op import delete_file


class FileDeleteHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["file_id"]

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - File
        summary: delete file from our system
        description: delete file
        parameters:
          - in: body
            name: body
            description: delete info
            required: true
            schema:
              type: object
              required:
                - file_id
              properties:
                file_id:
                  type: string
        responses:
          '200':
            description: delete file successfully
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
        file_id = body.get("file_id")

        try:
            success = delete_file(file_id=file_id)
            if success:
                self.write({"status": success})
            else:
                self.write(
                    {
                        "errcode": Errcode.ErrFileDeleteFail.value,
                        "msg": translation_loader.translation.t("file.file_not_exist"),
                    }
                )
        except Exception as e:
            self.write({"errcode": Errcode.ErrFileDeleteFail.value, "msg": str(e)})


api_router.add("/api/file/remove", FileDeleteHandler)
