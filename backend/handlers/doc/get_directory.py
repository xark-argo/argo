import tkinter as tk
from collections.abc import Awaitable
from tkinter import filedialog
from typing import Optional

from core.errors.errcode import Errcode
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router


class DirectoryHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def get(self):
        """
        ---
        tags:
          - Doc
        summary: Get directory
        responses:
          '200':
            description: get directory
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    directory:
                      type: string
          '500':
            description: Invalid input
        """
        try:
            root = tk.Tk()
            root.lift()
            root.focus_force()
            root.withdraw()
            dir_path = filedialog.askdirectory()
            self.write({"directory": dir_path})
        except Exception as e:
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": str(e)})


api_router.add("/api/knowledge/get_directory", DirectoryHandler)
