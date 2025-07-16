import json
import logging
import mimetypes
import os
import threading
import time
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import cast

from configs.env import FOLDER_TREE_FILE
from core.file.file_db import FileDB
from models.document import DOCUMENTSTATUS
from services.doc import util
from services.doc.doc_db import CollectionDB, PartitionDB
from services.doc.milvus_op import DocCollectionOp
from services.doc.url_parse import RecursiveUrlLoader


class DocumentType(Enum):
    DOCUMENT_FILE = 0
    DOCUMENT_URL = 1
    DOCUMENT_DIALOGUE = 2


def init():
    process_file = threading.Thread(
        target=process_knowledge_base,
        args=(DocumentType.DOCUMENT_FILE.value,),
        daemon=True,
    )
    process_file.start()

    process_url = threading.Thread(
        target=process_knowledge_base,
        args=(DocumentType.DOCUMENT_URL.value,),
        daemon=True,
    )
    process_url.start()

    process_dialogue = threading.Thread(
        target=process_knowledge_base,
        args=(DocumentType.DOCUMENT_DIALOGUE.value,),
        daemon=True,
    )
    process_dialogue.start()

    knowledge_status_update = threading.Thread(target=update_knowledge_status, args=(), daemon=True)
    knowledge_status_update.start()

    sync_folder_task = threading.Thread(target=sync_folder, args=(), daemon=True)
    sync_folder_task.start()


def process_knowledge_base(document_type: int):
    while True:
        time.sleep(5)
        documents = PartitionDB.get_waiting_documents()

        if not documents:
            continue

        if documents:
            if document_type == DocumentType.DOCUMENT_FILE.value:
                documents = [each for each in documents if each.file_type != "url" and each.collection_name != "temp"]
            elif document_type == DocumentType.DOCUMENT_URL.value:
                documents = [each for each in documents if each.file_type == "url"]
            else:
                documents = [each for each in documents if each.collection_name == "temp"]

        if not documents:
            continue

        if document_type == DocumentType.DOCUMENT_URL.value:
            url_process = RecursiveUrlLoader(document=documents[0])
            url_process.upload()
        else:
            DocCollectionOp.upload_file(document=documents[0])


def update_knowledge_status():
    while True:
        time.sleep(5)
        try:
            collection_info_list = DocCollectionOp.list_collections()
            for collection_info in collection_info_list:
                partition_info_list = collection_info["partition_info"]
                if len(partition_info_list) == 0:
                    CollectionDB.update_collection_status(
                        collection_name=collection_info["collection_name"],
                        status=DOCUMENTSTATUS.FINISH.value,
                    )
                elif all(
                    each["document_status"] in {DOCUMENTSTATUS.FAIL.value, DOCUMENTSTATUS.DELETE.value}
                    for each in partition_info_list
                ):
                    fail_msg_list = []
                    for each in partition_info_list:
                        if each["document_status"] == DOCUMENTSTATUS.FAIL.value:
                            fail_msg_list.append(f"file_name: {each['document_name']}, fail_msg: {each['msg']}")
                    CollectionDB.update_collection_status(
                        collection_name=collection_info["collection_name"],
                        status=DOCUMENTSTATUS.FAIL.value,
                        message="\n".join(fail_msg_list),
                    )
                elif all(
                    each["document_status"]
                    in {
                        DOCUMENTSTATUS.FINISH.value,
                        DOCUMENTSTATUS.FAIL.value,
                        DOCUMENTSTATUS.DELETE.value,
                    }
                    for each in partition_info_list
                ):
                    CollectionDB.update_collection_status(
                        collection_name=collection_info["collection_name"],
                        status=DOCUMENTSTATUS.FINISH.value,
                    )
                elif collection_info["knowledge_status"] != DOCUMENTSTATUS.READY.value:
                    CollectionDB.update_collection_status(
                        collection_name=collection_info["collection_name"],
                        status=DOCUMENTSTATUS.WAITING.value,
                    )
        except Exception as ex:
            logging.exception("Update knowledge status failed")


def get_folder_newest_mtime(folder):
    latest_timestamp: float = 0
    file_num = 0
    for root, dirs, files in os.walk(folder):
        dir_mtime = os.path.getmtime(root)
        if dir_mtime > latest_timestamp:
            latest_timestamp = dir_mtime

        for file in files:
            if "." not in file:
                continue
            if file.startswith("."):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext not in [
                ".txt",
                ".docx",
                ".xlsx",
                ".xls",
                ".csv",
                ".pptx",
                ".ppt",
                ".pdf",
                ".md",
                ".json",
                ".html",
            ]:
                continue
            file_num += 1
            file_path = os.path.join(root, file)
            file_mtime = os.path.getmtime(file_path)
            if file_mtime > latest_timestamp:
                latest_timestamp = file_mtime
    return latest_timestamp, file_num


def sync_folder():
    while True:
        time.sleep(5)

        try:
            collection_map = defaultdict(list)
            for each in DocCollectionOp.list_collections():
                if folder := each.get("folder", ""):
                    collection_map[folder].append(each)

            for folder, collection_list in collection_map.items():
                folder_time, folder_file_num = get_folder_newest_mtime(folder)
                tree_file_time = os.path.getmtime(f"{folder}/{FOLDER_TREE_FILE}")
                local_file_map = util.get_file_list(folder)

                for current_collection in collection_list:
                    collection_name = cast(str, current_collection.get("collection_name"))
                    knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
                    if knowledge is None:
                        continue
                    user_id = knowledge.user_id
                    partition_list = current_collection.get("partition_info", [])
                    if (folder_time - tree_file_time < 0.000001) and (len(partition_list) != 0):
                        continue
                    if folder_file_num == 0 and len(partition_list) == 0:
                        continue
                    logging.info(f"knowledge_name: {knowledge.knowledge_name} folder change: {folder}")
                    new_file_list = list(
                        set(local_file_map.keys())
                        - {
                            document.get("document_url").replace("/api/documents/", "").split(".")[0]
                            for document in partition_list
                        }
                    )
                    for document in partition_list:
                        document_url = document.get("document_url").replace("/api/documents/", "")
                        file_id = document_url.split(".")[0]
                        file_name = document.get("document_name")
                        partition_name = document.get("partition_name")
                        if file_id not in local_file_map:
                            DocCollectionOp.drop_partition(
                                collection_name=collection_name,
                                partition_name=partition_name,
                            )
                        elif file_name != local_file_map[file_id]:
                            PartitionDB.update_document_name(partition_name=partition_name, file_name=file_name)
                            FileDB.update_file_name(
                                user_id=user_id,
                                file_id=document_url,
                                file_name=file_name,
                            )

                    for file_sha256 in new_file_list:
                        each_file = local_file_map[file_sha256]
                        extension = os.path.splitext(each_file)[1]
                        file_name = os.path.basename(each_file)
                        file_id = f"{file_sha256}{extension}"
                        file = FileDB.get_file_by_id(file_id=file_id)
                        file_size = os.path.getsize(each_file)
                        if not file:
                            FileDB.create_new_file(
                                user_id=user_id,
                                file_id=file_id,
                                file_name=file_name,
                                file_size=file_size,
                            )
                        content_type, _ = mimetypes.guess_type(each_file)
                        if not content_type:
                            content_type = file_name.split(".")[-1]
                        _ = PartitionDB.create_document(
                            collection_name=collection_name,
                            file_id=file_id,
                            file_name=file_name,
                            file_url=f"/api/documents/{file_id}",
                            file_type=content_type,
                            file_size=file_size,
                            description=file_name,
                            progress=0.0,
                        )

                path = Path(folder) / FOLDER_TREE_FILE
                path.write_text(
                    json.dumps(local_file_map, indent=4, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception as ex:
            logging.exception("An unexpected error occurred.")
