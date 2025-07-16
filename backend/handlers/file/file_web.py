import json
import logging
import os
from pathlib import Path
from urllib.parse import quote

from configs.env import ARGO_STORAGE_PATH_DOCUMENTS, FOLDER_TREE_FILE, PROJECT_ROOT
from core.file.file_db import FileDB
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseRequestHandler
from handlers.router import api_router
from services.doc.doc_db import CollectionDB, PartitionDB


class FileWebHandler(BaseRequestHandler):
    def __init__(self, *args, **kwargs):
        self.path = kwargs.pop("path", "")
        super().__init__(*args, **kwargs)

    def set_default_headers(self):
        origin = self.request.headers.get("Origin", "*")
        self.set_header("Access-Control-Allow-Origin", origin)
        self.set_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Content-Disposition, Authorization, X-Custom-Header, Baggage, sentry-trace",
        )
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.set_header("Access-Control-Allow-Credentials", "true")

    def options(self, file):
        self.set_status(200)
        self.finish()

    def get(self, file):
        file_path = os.path.join(self.path, file)
        file_in_db = FileDB.get_file_by_id(file_id=file)
        knowledge = None
        try:
            document = PartitionDB.get_document_by_file_id(file_id=file)
            if document:
                knowledge = CollectionDB.get_collection_by_name(collection_name=document.collection_name)
                if knowledge and knowledge.folder:
                    folder_path = Path(knowledge.folder)
                    tree_file = folder_path / FOLDER_TREE_FILE
                    with tree_file.open(encoding="utf-8") as fp:
                        tree_info = json.loads(fp.read())
                        file_hash, _ = os.path.splitext(file)
                        file_path = tree_info[file_hash]
        except Exception as ex:
            logging.exception("An unexpected error occurred.")

        if os.path.isfile(file_path):
            if file_in_db:
                if knowledge and knowledge.folder:
                    file_name = os.path.basename(file_path)
                else:
                    file_name = file_in_db.file_name
                encoded_file_name = quote(file_name)
                self.set_header("Content-Type", "application/octet-stream; charset=utf-8")
                self.set_header("Content-Disposition", f'attachment; filename="{encoded_file_name}"')
            else:
                encoded_file_name = Path(file_path).name
                self.set_header("Content-Type", "application/octet-stream; charset=utf-8")
                self.set_header("Content-Disposition", f'attachment; filename="{encoded_file_name}"')

            with open(file_path, "rb") as f:
                while chunk := f.read(4096):
                    self.write(chunk)
            self.finish()
        else:
            self.set_status(404)
            self.write(translation_loader.translation.t("file.file_not_found"))


(api_router.add(r"/api/documents/(.*)", FileWebHandler, {"path": ARGO_STORAGE_PATH_DOCUMENTS}))
(api_router.add(r"/api/files/(.*)", FileWebHandler, {"path": PROJECT_ROOT}))
