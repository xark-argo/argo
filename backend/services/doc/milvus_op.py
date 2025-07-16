import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Union

from qdrant_client import models
from tqdm import tqdm

from configs.env import (
    ARGO_STORAGE_PATH_DOCUMENTS,
    FOLDER_TREE_FILE,
    MILVUS_DISTANCE_METHOD,
)
from configs.settings import FILE_SETTINGS
from core.file.file_db import FileDB
from core.i18n.translation import translation_loader
from core.model_providers import model_provider_manager
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_model_exist
from core.tracking.client import KnowledgeTrackingPayload, argo_tracking
from database.vector import get_qdrant_client
from models.document import DOCUMENTSTATUS, Document
from services.common.provider_setting_service import get_provider_setting
from services.doc import util
from services.doc.doc_db import CollectionDB, PartitionDB
from utils.path import app_path


class DocCollectionOp:
    @staticmethod
    def create_collection(
        user_id: str,
        knowledge_name: str,
        description: str,
        provider: str,
        embedding_model: str = "nomic-embed-text:latest",
        chunk_size: int = FILE_SETTINGS["CHUNK_SIZE"],
        chunk_overlap: int = FILE_SETTINGS["CHUNK_OVERLAP"],
        top_k: int = FILE_SETTINGS["TOP_K"],
        folder: str = "",
        similarity_threshold: float = 0.0,
        index_type: str = "HNSW",
        metric_type: str = MILVUS_DISTANCE_METHOD,
        params=None,
    ) -> dict:
        if params is None:
            params = DocCollectionOp.get_default_index_params(index_type=index_type)
        if embedding_model != "":
            try:
                embedding = model_provider_manager.get_embedding_instance(provider, embedding_model)
                vectors = embedding.embed_query("test")
                dimension = len(vectors)
                logging.info(f"use embedding model: {embedding_model}, dimension: {dimension}")
            except Exception:
                dimension = 768
                logging.exception(f"Failed to create embedding instance for provider '{provider}'")
        else:
            dimension = 768
            logging.info(f"using default dimension: {dimension}")

        index_params = {
            "index_type": index_type,
            "metric_type": metric_type,
            "params": params,
        }
        collection_name = CollectionDB.store_collection_info(
            user_id=user_id,
            knowledge_name=knowledge_name,
            description=description,
            provider=provider,
            embedding_model=embedding_model,
            similarity_threshold=similarity_threshold,
            index_params=index_params,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_k=top_k,
            folder=folder,
        )

        hnsw_config = models.HnswConfigDiff(
            m=index_params.get("M", 64),
            ef_construct=index_params.get("efConstruction", 512),
        )
        vectors_config = models.VectorParams(
            size=dimension,
            datatype=models.Datatype.FLOAT16,
            distance=models.Distance.COSINE,
            hnsw_config=hnsw_config,
        )
        get_qdrant_client().create_collection(collection_name=collection_name, vectors_config=vectors_config)
        get_qdrant_client().create_payload_index(
            collection_name,
            "page_content",
            field_schema="keyword",
        )
        get_qdrant_client().create_payload_index(
            collection_name,
            "metadata",
            field_schema="keyword",
        )

        CollectionDB.update_collection_status(collection_name=collection_name, status=DOCUMENTSTATUS.FINISH.value)

        argo_tracking(
            KnowledgeTrackingPayload(
                embedding_model=embedding_model,
            )
        )
        return {"success": True, "collection_name": collection_name}

    @staticmethod
    def drop_collection(collection_name: str):
        if collection_name in [col.name for col in get_qdrant_client().get_collections().collections]:
            get_qdrant_client().delete_collection(collection_name=collection_name)
            logging.info(f"drop collection {collection_name}")

        documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
        knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
        CollectionDB.drop_collection_by_name(collection_name=collection_name)
        for document in documents:
            site_count = PartitionDB.get_document_site_count(file_id=document.file_id)
            if knowledge and knowledge.folder:
                # with open(f"{knowledge.folder}/{FOLDER_TREE_FILE}") as fp:
                #     tree_info = json.loads(fp.read())
                #     file_hash, _ = os.path.splitext(document.file_id)
                #     file_path = tree_info[file_hash]
                #     if os.path.isfile(file_path):
                #         os.remove(file_path)
                pass
            else:
                if site_count == 0:
                    if os.path.isfile(f"{ARGO_STORAGE_PATH_DOCUMENTS}/{document.file_id}"):
                        os.remove(f"{ARGO_STORAGE_PATH_DOCUMENTS}/{document.file_id}")
            if site_count == 0:
                FileDB.delete_file(file_id=document.file_id)

    @staticmethod
    def upload_file(document: Document):
        if document is None:
            return

        try:
            knowledge = CollectionDB.get_collection_by_name(collection_name=document.collection_name)
            if knowledge is None:
                return
            if knowledge.knowledge_status != DOCUMENTSTATUS.WAITING.value:
                return

            file_path = os.path.join(ARGO_STORAGE_PATH_DOCUMENTS, document.file_url.split("/")[-1])
            if knowledge.folder:
                folder_tree_path = Path(knowledge.folder) / FOLDER_TREE_FILE
                with folder_tree_path.open(encoding="utf-8") as fp:
                    tree_info = json.loads(fp.read())
                    file_path = tree_info[document.file_url.split("/")[-1].split(".")[0]]
            if not os.path.exists(file_path):
                raise Exception(f"file {file_path} not exist")
            origin_data, docs, known_type = util.get_docs(
                file_path=file_path,
                file_type=document.file_type,
                chunk_size=(knowledge.chunk_size or FILE_SETTINGS["CHUNK_SIZE"]),
                chunk_overlap=(knowledge.chunk_overlap or FILE_SETTINGS["CHUNK_OVERLAP"]),
            )
            logging.info(f"starting process file_name: {document.file_name}, file_url: {document.file_url}")
            if len(docs) <= 0:
                PartitionDB.update_status(
                    partition_name=document.partition_name,
                    status=DOCUMENTSTATUS.FAIL.value,
                    msg=f"document {document.file_name} is empty",
                )
                return

            texts = [doc.page_content for doc in docs]
            metadatas = [doc.metadata for doc in docs]
            content = ""
            content_length = 0
            for doc in origin_data:
                content += doc.page_content
                content_length += len(doc.page_content)
            if content_length > 1000000:
                content = ""
            PartitionDB.update_content_info(
                partition_name=document.partition_name,
                content=content,
                content_length=content_length,
            )

            # 临时知识库单独处理 结束后直接返回
            if document.collection_name == "temp":
                if content_length <= 1000000:
                    PartitionDB.update_progress(partition_name=document.partition_name, progress=1.0)
                    PartitionDB.update_status(
                        partition_name=document.partition_name,
                        status=DOCUMENTSTATUS.FINISH.value,
                    )
                else:
                    PartitionDB.update_status(
                        partition_name=document.partition_name,
                        status=DOCUMENTSTATUS.FAIL.value,
                        msg=f"document {document.file_name} too large, "
                        f"content length is {content_length}, exceed 1000K",
                    )
                return

            if not knowledge.provider:  # 兼容老版本
                knowledge.provider = OLLAMA_PROVIDER

            providerSt = get_provider_setting(knowledge.provider)
            if not providerSt:
                raise ValueError(f"Please set provider for {knowledge.provider}")

            # 知识库embedding处理流程
            if knowledge.provider == OLLAMA_PROVIDER:
                if not ollama_model_exist(providerSt.safe_base_url, knowledge.embedding_model):
                    return

            logging.info(f"store_data_in_vector_db: {len(docs)}")
            collection_name = document.collection_name
            partition_name = document.partition_name

            if not get_qdrant_client().collection_exists(collection_name):
                try:
                    embedding = model_provider_manager.get_embedding_instance(
                        knowledge.provider, knowledge.embedding_model
                    )
                    vectors = embedding.embed_query("test")
                    dimension = len(vectors)
                except Exception:
                    dimension = 768
                    logging.exception(f"Failed to create embedding instance for provider '{knowledge.provider}'")

                index_params: dict[str, Any] = {}
                hnsw_config = models.HnswConfigDiff(
                    m=index_params.get("M", 64),
                    ef_construct=index_params.get("efConstruction", 512),
                )
                vectors_config = models.VectorParams(
                    size=dimension,
                    datatype=models.Datatype.FLOAT16,
                    distance=models.Distance.COSINE,
                    hnsw_config=hnsw_config,
                )
                get_qdrant_client().create_collection(collection_name, vectors_config=vectors_config)
                get_qdrant_client().create_payload_index(
                    collection_name,
                    "page_content",
                    field_schema="keyword",
                )
                get_qdrant_client().create_payload_index(
                    collection_name,
                    "metadata",
                    field_schema="keyword",
                )

            col_info = get_qdrant_client().get_collection(collection_name=collection_name)
            if col_info:
                get_qdrant_client().delete_payload_index(collection_name, partition_name)

                get_qdrant_client().delete(
                    collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key=partition_name,
                                    match=models.MatchValue(value="1"),
                                )
                            ]
                        )
                    ),
                )

            get_qdrant_client().create_payload_index(
                document.collection_name,
                document.partition_name,
                field_schema="keyword",
            )

            embedding_texts = [x.replace("\n", " ") for x in texts]
            batch_size = 20
            with tqdm(
                total=len(embedding_texts),
                initial=0,
                unit="B",
                unit_scale=True,
                desc=f"processing {document.file_name}",
                ascii=True,
            ) as progress_bar:
                i = -1
                for i in range(len(embedding_texts) // batch_size):
                    document_count = PartitionDB.get_document_count(partition_name=document.partition_name)
                    if document_count == 0:
                        return

                    try:
                        embedding = model_provider_manager.get_embedding_instance(
                            knowledge.provider, knowledge.embedding_model
                        )
                        embedded_vectors = embedding.embed_documents(
                            embedding_texts[i * batch_size : (i + 1) * batch_size]
                        )
                    except Exception:
                        progress_bar.update(batch_size)
                        progress = round(progress_bar.n / progress_bar.total, 2)
                        PartitionDB.update_progress(partition_name=document.partition_name, progress=progress)
                        logging.exception(f"Failed to create embedding instance for provider '{knowledge.provider}'")
                        continue

                    try:
                        points = []
                        for j in range(batch_size):
                            payload = {
                                "page_content": embedding_texts[i * batch_size + j],
                                document.partition_name: "1",
                                "metadata": metadatas[i * batch_size + j],
                            }

                            points.append(
                                models.PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=embedded_vectors[j],
                                    payload=payload,
                                )
                            )

                        get_qdrant_client().upsert(
                            document.collection_name,
                            points=points,
                            wait=False,
                        )
                    except Exception as ex:
                        logging.exception("Failed to upsert points to qdrant.")

                    progress_bar.update(batch_size)
                    progress = round(progress_bar.n / progress_bar.total, 2)
                    PartitionDB.update_progress(partition_name=document.partition_name, progress=progress)
                if i == -1 or (i + 1) * batch_size < len(embedding_texts):
                    try:
                        embedding = model_provider_manager.get_embedding_instance(
                            knowledge.provider, knowledge.embedding_model
                        )
                        embedded_vectors = embedding.embed_documents(embedding_texts[(i + 1) * batch_size :])

                        points = []
                        for j in range(len(embedding_texts) - (i + 1) * batch_size):
                            payload = {
                                "page_content": embedding_texts[(i + 1) * batch_size + j],
                                document.partition_name: "1",
                                "metadata": metadatas[(i + 1) * batch_size + j],
                            }

                            points.append(
                                models.PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=embedded_vectors[j] if embedded_vectors else [],
                                    payload=payload,
                                )
                            )

                        get_qdrant_client().upsert(
                            document.collection_name,
                            points=points,
                            wait=False,
                        )

                    except Exception as ex:
                        logging.exception("Failed to upsert points to qdrant.")
                    progress_bar.update(len(embedding_texts) - (i + 1) * batch_size)
                    progress = round(progress_bar.n / progress_bar.total, 2)
                    PartitionDB.update_progress(partition_name=document.partition_name, progress=progress)
                PartitionDB.update_status(
                    partition_name=document.partition_name,
                    status=DOCUMENTSTATUS.FINISH.value,
                )
                DocCollectionOp.rebuild_index(document.collection_name)
                CollectionDB.update_collection_field(collection_name=document.collection_name)
        except RuntimeError as run_ex:
            logging.exception("Upload file failed.")
            if "Could not detect encoding" in str(run_ex):
                PartitionDB.update_status(
                    partition_name=document.partition_name,
                    status=DOCUMENTSTATUS.FAIL.value,
                    msg=translation_loader.translation.t("doc.document_encoding_fail", ex=run_ex),
                )
            else:
                PartitionDB.update_status(
                    partition_name=document.partition_name,
                    status=DOCUMENTSTATUS.FAIL.value,
                    msg=str(run_ex),
                )
        except Exception as ex:
            logging.exception("Upload file failed")
            PartitionDB.update_status(
                partition_name=document.partition_name,
                status=DOCUMENTSTATUS.FAIL.value,
                msg=str(ex),
            )

    @staticmethod
    def drop_partition(collection_name: str, partition_name: str):
        col_info = get_qdrant_client().get_collection(collection_name=collection_name)
        if col_info:
            try:
                get_qdrant_client().delete_payload_index(collection_name, partition_name)
                get_qdrant_client().delete(
                    collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key=partition_name,
                                    match=models.MatchValue(value="1"),
                                )
                            ]
                        )
                    ),
                )
            except Exception as ex:
                logging.exception("Failed to drop partition.")
                return False

        knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)

        if knowledge and knowledge.folder:
            partition = PartitionDB.get_partition_by_partition_name(partition_name=partition_name)
            file_id = partition.file_id if partition else ""
            folder_tree_path = Path(knowledge.folder) / FOLDER_TREE_FILE
            with folder_tree_path.open(encoding="utf-8") as fp:
                tree_info = json.loads(fp.read())
                file_hash, _ = os.path.splitext(file_id)
                if file_hash in tree_info:
                    file_path = tree_info[file_hash]
                    if not os.path.exists(file_path):
                        PartitionDB.drop_document(partition_name=partition_name)
                    else:
                        PartitionDB.update_status(
                            partition_name=partition_name,
                            status=DOCUMENTSTATUS.DELETE.value,
                        )
                else:
                    PartitionDB.drop_document(partition_name=partition_name)
        else:
            file_id = PartitionDB.drop_document(partition_name=partition_name)
            site_count = PartitionDB.get_document_site_count(file_id=file_id)
            if site_count == 0:
                if os.path.isfile(f"{ARGO_STORAGE_PATH_DOCUMENTS}/{file_id}"):
                    os.remove(f"{ARGO_STORAGE_PATH_DOCUMENTS}/{file_id}")
            if site_count == 0:
                FileDB.delete_file(file_id=file_id)

        CollectionDB.update_collection_field(collection_name=collection_name)
        return True

    @staticmethod
    def rebuild_index(collection_name: str):
        pass

        # index_params = {
        #     "index_type": "HNSW",
        #     "metric_type": MILVUS_DISTANCE_METHOD,
        #     "params": DocCollectionOp.get_default_index_params(index_type="HNSW")
        # }
        # index_params_input = IndexParams(field_name='vector', **index_params)
        # index_names = get_client().list_indexes(collection_name=collection_name)
        # get_client().release_collection(collection_name=collection_name)
        # for index_name in index_names:
        #     get_client().drop_index(collection_name=collection_name, index_name=index_name)
        # get_client().create_index(collection_name=collection_name, index_params=index_params_input)

    @staticmethod
    def get_default_index_params(index_type: str) -> dict:
        if index_type == "FLAT":
            return {}
        elif index_type in {"IVF_FLAT", "IVF_SQ8"}:
            return {
                "nlist": 1024,
            }
        elif index_type == "IVF_PQ":
            return {
                "nlist": 1024,
                "m": 7,
                "nbits": 8,
            }
        elif index_type in {"HNSW", "RHNSW_FLAT"}:
            return {"M": 64, "efConstruction": 512}
        elif index_type == "RHNSW_PQ":
            return {"M": 64, "efConstruction": 512, "PQM": 7}
        elif index_type == "ANNOY":
            return {"n_trees": 1024}

        return {}

    @staticmethod
    def list_collections() -> list[dict]:
        cols = get_qdrant_client().get_collections()
        collection_names = [col.name for col in cols.collections]
        db_collection_names = [
            col.collection_name
            for col in CollectionDB.get_all_db_collections()
            if col.knowledge_status not in [DOCUMENTSTATUS.WAITING.value, DOCUMENTSTATUS.READY.value]
        ]

        to_delete_collections = list(set(db_collection_names) - set(collection_names))
        for collection_name in to_delete_collections:
            documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
            knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
            CollectionDB.drop_collection_by_name(collection_name=collection_name)
            for document in documents:
                site_count = PartitionDB.get_document_site_count(file_id=document.file_id)
                if knowledge and knowledge.folder:
                    tree_file_path = Path(knowledge.folder) / FOLDER_TREE_FILE
                    with tree_file_path.open(encoding="utf-8") as fp:
                        tree_info = json.loads(fp.read())
                        file_hash, _ = os.path.splitext(document.file_id)
                        file_path = tree_info[file_hash]
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                else:
                    if site_count == 0:
                        if os.path.isfile(f"{ARGO_STORAGE_PATH_DOCUMENTS}/{document.file_id}"):
                            os.remove(f"{ARGO_STORAGE_PATH_DOCUMENTS}/{document.file_id}")
                if site_count == 0:
                    FileDB.delete_file(file_id=document.file_id)
        info = []
        for collection in collection_names:
            collection_info = DocCollectionOp.show_collection_info(collection_name=collection)
            if collection_info:
                info.append(collection_info)
        return info

    @staticmethod
    def show_collection_info(
        collection_name: str,
    ) -> dict[str, Union[str, int, float, dict, list[dict[str, Union[str, float, int]]]]]:
        knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
        if knowledge is None:
            return {}
        documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
        return {
            "knowledge_name": knowledge.knowledge_name,
            "knowledge_status": knowledge.knowledge_status,
            "collection_name": collection_name,
            "description": knowledge.description,
            "provider": knowledge.provider or OLLAMA_PROVIDER,
            "embedding_model": knowledge.embedding_model,
            "similarity_threshold": knowledge.similarity_threshold,
            "chunk_size": (FILE_SETTINGS["CHUNK_SIZE"] if knowledge.chunk_size is None else knowledge.chunk_size),
            "chunk_overlap": (
                FILE_SETTINGS["CHUNK_OVERLAP"] if knowledge.chunk_overlap is None else knowledge.chunk_overlap
            ),
            "top_k": (FILE_SETTINGS["TOP_K"] if knowledge.top_k is None else knowledge.top_k),
            "folder": "" if knowledge.folder is None else knowledge.folder,
            "index_params": knowledge.index_params,
            "create_at": int(knowledge.create_at.timestamp()),
            "update_at": int(knowledge.update_at.timestamp()),
            "partition_info": [
                {
                    "partition_name": document.partition_name,
                    "document_name": document.file_name,
                    "document_url": document.file_url,
                    "file_type": document.file_type,
                    "file_size": document.file_size,
                    "description": document.description,
                    "progress": document.progress,
                    "document_status": document.document_status,
                    "document_path": app_path(
                        os.sep.join(
                            [
                                (ARGO_STORAGE_PATH_DOCUMENTS if not knowledge.folder else knowledge.folder),
                                (
                                    document.file_url.removeprefix("/api/documents/")
                                    if not knowledge.folder
                                    else os.path.basename(document.file_name)
                                ),
                            ]
                        )
                    ),
                    "msg": document.msg,
                    "create_at": int(document.create_at.timestamp()),
                    "update_at": int(document.update_at.timestamp()),
                }
                for document in documents
            ],
        }

    @staticmethod
    def list_collections_by_user_id(user_id: str) -> list[dict]:
        collections = CollectionDB.get_collection_by_user_id(user_id)
        info = []
        for collection in collections:
            if collection.collection_name == "temp":
                continue
            collection_info = DocCollectionOp.show_collection_info(collection_name=collection.collection_name)
            if collection_info:
                info.append(collection_info)
        return info

    @staticmethod
    def update_collection(
        collection_name: str,
        knowledge_name: str,
        description: str,
        provider: str,
        embedding_model: str,
        similarity_threshold: float,
        dimension: int,
        chunk_size: int,
        chunk_overlap: int,
        top_k: int,
        folder: str,
    ) -> bool:
        collection_info = DocCollectionOp.show_collection_info(collection_name=collection_name)
        if not collection_info:
            return False
        if (
            knowledge_name == collection_info.get("knowledge_name")
            and description == collection_info.get("description")
            and embedding_model == collection_info.get("embedding_model")
            and similarity_threshold == collection_info.get("similarity_threshold")
            and collection_info.get("chunk_size") == chunk_size
            and collection_info.get("chunk_overlap") == chunk_overlap
            and collection_info.get("top_k") == top_k
            and collection_info.get("folder") == folder
        ):
            return False
        else:
            embed_change = (
                embedding_model != collection_info.get("embedding_model")
                or chunk_overlap != collection_info.get("chunk_overlap")
                or chunk_size != collection_info.get("chunk_size")
            )
            CollectionDB.update_collection(
                collection_info=collection_info,
                knowledge_name=knowledge_name,
                description=description,
                provider=provider,
                embedding_model=embedding_model,
                embed_change=embed_change,
                similarity_threshold=similarity_threshold,
                dimension=dimension,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                top_k=top_k,
                folder=folder,
            )
            return True
