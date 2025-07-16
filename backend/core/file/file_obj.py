import base64
import enum
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from configs.env import ARGO_STORAGE_PATH_DOCUMENTS
from models.document import DOCUMENTSTATUS, get_partition_by_partition_name

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif", "svg"]
IMAGE_EXTENSIONS.extend([ext.upper() for ext in IMAGE_EXTENSIONS])


class FileType(enum.Enum):
    IMAGE = "image"
    DOCUMENT = "document"

    @staticmethod
    def value_of(value):
        for member in FileType:
            if member.value == value:
                return member
        raise ValueError(f"No matching enum found for value '{value}'")


class FileTransferMethod(enum.Enum):
    REMOTE_URL = "remote_url"
    LOCAL_FILE = "local_file"

    @staticmethod
    def value_of(value):
        for member in FileTransferMethod:
            if member.value == value:
                return member
        raise ValueError(f"No matching enum found for value '{value}'")


class FileVar(BaseModel):
    workspace_id: str
    type: FileType
    transfer_method: FileTransferMethod
    url: Optional[str] = None  # remote url
    related_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "__variant": self.__class__.__name__,
            "workspace_id": self.workspace_id,
            "type": self.type.value,
            "transfer_method": self.transfer_method.value,
            "url": self.preview_url,
            "related_id": self.related_id,
        }

    @property
    def data(self) -> Optional[str]:
        """
        Get image data, file signed url or base64 data
        depending on config MULTIMODAL_SEND_IMAGE_FORMAT
        :return:
        """
        return self._get_data()

    @property
    def preview_url(self) -> Optional[str]:
        """
        Get signed preview url
        :return:
        """
        return self._get_data()

    @property
    def prompt_message_content(self) -> dict[str, Any]:
        if self.type == FileType.IMAGE:
            return {
                "type": "image_url",
                "image_url": {"url": self.data, "detail": "auto"},
            }
        elif self.type == FileType.DOCUMENT:
            return {"type": "text", "text": f"\n{self.data}"}

    def _get_data(self) -> Optional[str]:
        if self.type == FileType.IMAGE:
            if self.transfer_method == FileTransferMethod.REMOTE_URL:
                return self.url
            elif self.transfer_method == FileTransferMethod.LOCAL_FILE:
                return self.get_image_data()
        elif self.type == FileType.DOCUMENT:
            return self.get_document_data()

        return None

    def get_document_data(self) -> Optional[str]:
        if not self.related_id:
            return None

        doc = get_partition_by_partition_name(partition_name=self.related_id)
        if not doc or doc.document_status != DOCUMENTSTATUS.FINISH.value:
            return None

        return f"{doc.file_name}\n{doc.content}"

    def get_image_data(self) -> Optional[str]:
        if not self.related_id:
            return None

        file_path = os.path.join(ARGO_STORAGE_PATH_DOCUMENTS, self.related_id)

        extension = file_path.split(".")[-1]
        if extension not in IMAGE_EXTENSIONS:
            return None

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            return None

        # get image file base64
        try:
            data = Path(file_path).read_bytes()
        except FileNotFoundError:
            logging.exception(f"File not found: {file_path}")
            return None

        encoded_string = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{encoded_string}"
