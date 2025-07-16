import logging
from collections.abc import Awaitable
from typing import Optional

from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.file.file_op import upload_file


class FileUploadHandler(BaseProtectedHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def post(self):
        """
        ---
        tags:
          - File
        summary: Upload a file
        requestBody:
          required: true
          content:
            multipart/form-data:
              schema:
                type: object
                properties:
                  file_path:
                    type: string
                    format: binary
        responses:
          200:
            description: File uploaded successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    message:
                      type: string
                    file_id:
                      type: string
                    file_name:
                      type: string
                    file_url:
                      type: string
          400:
            description: Invalid request or failed to upload file
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    error:
                      type: string
        """
        try:
            file_meta = self.request.files["file_path"][0]
            file_name = file_meta["filename"]
            file_content = file_meta["body"]
            user_id = self.current_user.id

            result = upload_file(user_id=user_id, file_name=file_name, file_content=file_content)
            result["file_url"] = f"/api/documents/{result['file_id']}"
            result["file_name"] = file_name
            self.write(result)
        except Exception as ex:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrFileUploadFail.value,
                    "msg": translation_loader.translation.t("file.file_upload_fail", ex=str(ex)),
                }
            )


class MultiFileUploadHandler(BaseProtectedHandler):
    def post(self):
        """
        ---
        tags:
          - File
        summary: Upload multiple files
        description: Handles the upload of multiple files and stores them.
        consumes:
          - multipart/form-data
        parameters:
          - in: formData
            name: files
            description: List of files to upload
            required: true
            type: array
            items:
              type: file
        responses:
          200:
            description: Files uploaded successfully
            schema:
              type: object
              properties:
                files:
                  type: array
                  items:
                    type: object
                    properties:
                      file_id:
                        type: string
                      file_name:
                        type: string
                      file_url:
                        type: string
          400:
            description: No files uploaded
          500:
            description: Internal server error
        """
        try:
            files = self.request.files.get("files", [])
            if not files:
                self.set_status(400)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeInvalidRequest.value,
                        "msg": "No files uploaded.",
                    }
                )
                return

            user_id = self.current_user.id
            uploaded_files = []

            for file_meta in files:
                file_name = file_meta["filename"]
                file_content = file_meta["body"]

                result = upload_file(user_id=user_id, file_name=file_name, file_content=file_content)
                uploaded_files.append(
                    {
                        "file_id": result["file_id"],
                        "file_name": file_name,
                        "file_url": f"/api/documents/{result['file_id']}",
                    }
                )

            self.write({"files": uploaded_files})

        except Exception as e:
            logging.exception("internal server error.")
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": str(e)})


api_router.add("/api/file/upload", FileUploadHandler)
api_router.add("/api/file/upload_multiple", MultiFileUploadHandler)
