import logging
import mimetypes
from collections.abc import Awaitable
from datetime import datetime
from io import BytesIO
from typing import Optional

from configs.env import ARGO_STORAGE_PATH_DOCUMENTS
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.bot import get_bot, get_model_config
from models.document import DOCUMENTSTATUS
from services.doc import util
from services.doc.doc_db import CollectionDB, PartitionDB
from services.doc.util import get_loader
from services.file.file_op import upload_file


class UploadDocumentsHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - Doc
        summary: Upload documents and create partitions
        description: Create partition
        requestBody:
          required: true
          content:
            multipart/form-data:
              schema:
                type: object
                properties:
                  files:
                    type: array
                    items:
                      type: string
                      format: binary
                    description: List of files to upload
                  collection_name:
                    type: string
                    description: Collection unique name
                  description:
                    type: string
                    description: file group description
                  bot_id:
                    type: string
                    description: bot id
                required:
                  - files
                  - collection_name
        responses:
          '200':
            description: Upload documents successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    status:
                      type: boolean
                      description: When true, all files upload success; when false, some files upload fail
                    collection_name:
                      type: string
                      description: Collection name
                    success_file_names:
                      type: array
                      items:
                        type: string
                      description: Upload success file list
                    success_partition_names:
                      type: array
                      items:
                        type: string
                      description: Success partition list
                    failed_file_names:
                      type: array
                      items:
                        type: string
                      description: Upload fail file list
          '500':
            description: Invalid input
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    errcode:
                      type: integer
                      description: Error code
                    msg:
                      type: string
                      description: Error message
        """
        collection_name = self.get_argument("collection_name", "")
        knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
        if knowledge is None:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": translation_loader.translation.t(
                        "doc.knowledge_not_exists", collection_name=collection_name
                    ),
                }
            )
            return

        files = self.request.files.get("files", [])
        if len(files) == 0:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": translation_loader.translation.t("doc.document_empty"),
                }
            )
            return

        description = self.get_argument("description", "")
        bot_id = self.get_argument("bot_id", "")

        model_config = None
        bot = get_bot(bot_id) if bot_id else None
        if bot:
            model_config = get_model_config(bot.bot_model_config_id)

        illegal_file_names = []
        for file_meta in files:
            file_name = file_meta["filename"]
            if file_name == "blob":
                continue
            if "." not in file_name:
                illegal_file_names.append(file_name)

        if len(illegal_file_names) > 0:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": f"some files name illegal: {illegal_file_names}",
                }
            )
            return

        user_id = self.current_user.id
        failed_file_names = []
        success_file_names = []
        success_partition_names = []
        fail_messages = []

        base_folder = knowledge.folder or ARGO_STORAGE_PATH_DOCUMENTS
        for file_meta in files:
            file_name = file_meta["filename"]
            file_content = file_meta["body"]
            content_type = None
            if file_name == "blob":
                file_content = BytesIO(file_content).getvalue()
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
                content_type = "docx/html"
            result = upload_file(
                user_id=user_id,
                file_name=file_name,
                file_content=file_content,
                folder=base_folder,
            )
            rename_success = result["rename_success"]
            file_id = result["file_id"]
            file_url = f"/api/documents/{file_id}"
            file_size = result["file_size"]
            if rename_success:
                real_file_name = f"{base_folder}/{result['file_name']}"
                file_path = f"{base_folder}/{result['file_name']}"
            else:
                real_file_name = file_url.split("/")[-1]
                file_path = f"{base_folder}/{real_file_name}"

            if not content_type:
                content_type, _ = mimetypes.guess_type(file_path)
            logging.info(f"file content_type: {content_type}")

            if content_type is None:
                content_type = real_file_name.split(".")[-1]
            try:
                folder_patch = False
                if collection_name != "temp":
                    document_names = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
                    file_id_map = {document.file_id: document for document in document_names}
                    if file_id in file_id_map:
                        document = file_id_map[file_id]
                        if base_folder == ARGO_STORAGE_PATH_DOCUMENTS:
                            raise Exception(f"duplicate file {file_name}")
                        else:
                            folder_patch = True
                            PartitionDB.update_status(
                                partition_name=document.partition_name,
                                status=DOCUMENTSTATUS.WAITING.value,
                                msg="",
                            )
                            PartitionDB.update_progress(partition_name=document.partition_name, progress=0.0)
                            success_file_names.append(file_name)
                            success_partition_names.append(document.partition_name)
                if not folder_patch:
                    partition_name = PartitionDB.create_document(
                        collection_name=collection_name,
                        file_id=file_id,
                        file_name=file_name,
                        file_size=file_size,
                        file_url=file_url,
                        file_type=content_type,
                        description=description or file_name,
                        progress=0.0,
                    )
                    if model_config and not description:
                        loader, known_type = get_loader(real_file_name, content_type, file_path)
                        data = loader.load()
                        file_txt = ""
                        for each_chunk in data:
                            file_txt += each_chunk.page_content
                        description = util.generate_file_abstract(
                            bot_model_config=model_config, content=file_txt[:2000]
                        )
                        if description:
                            PartitionDB.update_description_name(partition_name=partition_name, desc_name=description)

                    success_file_names.append(file_name)
                    success_partition_names.append(partition_name)
            except Exception as ex:
                logging.exception("An unexpected exception occurred.")
                failed_file_names.append(file_name)
                fail_messages.append(str(ex))
        if len(failed_file_names) == len(files):
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrCreatePartitionFail.value,
                    "msg": f"failed documents: {failed_file_names}, fail reason: {','.join(fail_messages)}",
                }
            )
        else:
            if len(failed_file_names) > 0:
                self.write(
                    {
                        "status": False,
                        "collection_name": collection_name,
                        "success_file_names": success_file_names,
                        "success_partition_names": success_partition_names,
                        "failed_file_names": failed_file_names,
                    }
                )
            else:
                self.write(
                    {
                        "status": True,
                        "collection_name": collection_name,
                        "success_file_names": success_file_names,
                        "success_partition_names": success_partition_names,
                    }
                )


api_router.add("/api/knowledge/upload_document", UploadDocumentsHandler)
