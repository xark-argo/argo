import logging
import mimetypes
import os
from pathlib import Path

from configs.env import ARGO_STORAGE_PATH_DOCUMENTS
from core.file.file_db import FileDB
from services.doc import util
from utils.file_hash import calculate_content_sha256


def upload(file_path: str) -> bool:
    path = Path(file_path)
    if path.exists() and path.is_file():
        try:
            file_name = path.name
            content_type, _ = mimetypes.guess_type(str(path))
            logging.info(f"file content_type: {content_type}")

            save_file_path = Path(ARGO_STORAGE_PATH_DOCUMENTS) / file_name
            save_file_path.write_bytes(path.read_bytes())
            return True
        except Exception as e:
            logging.exception("Failed to upload file:")
            return False
    else:
        logging.warning(f"File not found or not a regular file: {file_path}")
        return False


def delete(file_name: str) -> bool:
    file_path = f"{ARGO_STORAGE_PATH_DOCUMENTS}/{file_name}"
    if os.path.exists(file_path) and os.path.isfile(file_path):
        os.remove(file_path)
        return True
    else:
        return False


def upload_file(
    user_id: str,
    file_name: str,
    file_content: bytes,
    folder: str = ARGO_STORAGE_PATH_DOCUMENTS,
) -> dict:
    file_sha256 = calculate_content_sha256(file_content)
    file_prefix, extension = os.path.splitext(file_name)
    rename_success = False
    if folder != ARGO_STORAGE_PATH_DOCUMENTS:
        local_file_map = util.get_file_list(folder)
        if file_sha256 in local_file_map:
            save_file_path = local_file_map[file_sha256]
            file_name = os.path.basename(save_file_path)
        else:
            save_file_path = f"{folder}/{file_name}"
            if os.path.exists(save_file_path):
                for i in range(1000):
                    save_file_path = f"{folder}/{file_prefix}_{i}{extension}"
                    if not os.path.exists(save_file_path):
                        rename_success = True
                        file_name = f"{file_prefix}_{i}{extension}"
                        break
            else:
                rename_success = True
            if not rename_success:
                save_file_path = f"{folder}/{file_sha256}{extension}"
                file_name = f"{file_prefix}{extension}"

            Path(save_file_path).write_bytes(file_content)
    else:
        file_path = Path(folder) / f"{file_sha256}{extension}"
        if not file_path.exists():
            file_path.write_bytes(file_content)

    file_id = f"{file_sha256}{extension}"
    db_file = FileDB.get_file_by_id(file_id=file_id)
    if db_file is None:
        FileDB.create_new_file(
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            file_size=len(file_content),
        )
        return {
            "file_id": file_id,
            "file_name": file_name,
            "file_size": len(file_content),
            "rename_success": rename_success,
        }
    else:
        return {
            "file_id": file_id,
            "file_name": file_name,
            "file_size": len(file_content),
            "rename_success": rename_success,
        }


def delete_file(file_id: str) -> bool:
    file = FileDB.get_file_by_id(file_id)
    if file is None:
        return False
    file_name = file.file_name
    file_path = f"{ARGO_STORAGE_PATH_DOCUMENTS}/{file_name}"
    if os.path.exists(file_path) and os.path.isfile(file_path):
        os.remove(file_path)
        FileDB.delete_file(file_id)
        return True
    else:
        return False
