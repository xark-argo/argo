import logging
import platform

import tornado
import tornado.web
from tornado.web import StaticFileHandler

from handlers.router import api_router
from utils.path import app_path


class CustomStaticFileHandler(StaticFileHandler):
    def _log(self):
        return

    if platform.system() == "Windows":
        # Replace the mimetype for .js, as there can be potentially broken
        # entries in the windows registry:
        import mimetypes

        mimetypes.add_type("application/javascript", ".js", strict=True)

    async def get(self, path, *args, **kwargs):
        try:
            return await super().get(path, *args, **kwargs)
        except Exception as e:
            if isinstance(e, tornado.web.HTTPError) and e.status_code == 404:
                return await super().get("index.html", *args, **kwargs)
            logging.exception("Unhandled error while serving static file.")


api_router.add(
    r"/(.*)",
    CustomStaticFileHandler,
    {"path": app_path("dist"), "default_filename": "index.html"},
)
