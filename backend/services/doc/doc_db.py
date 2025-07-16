import logging
import uuid
from datetime import datetime
from typing import Optional, Union

from qdrant_client import models
from sqlalchemy.exc import SQLAlchemyError

from configs.settings import FILE_SETTINGS
from core.tracking.client import DocumentTrackingPayload, argo_tracking
from database.db import session_scope
from database.vector import get_qdrant_client
from models.dataset import PERMISSION, Dataset
from models.document import DOCUMENTSTATUS, Document
from models.knowledge import Knowledge


class DocDB:
    @staticmethod
    def create_new_doc(
        space_id,
        bot_id,
        description,
        user_id,
        collection_name,
        embedding_model: str = "nomic-embed-text:latest",
        permission: int = PERMISSION.ALL_USER.value,
    ):
        with session_scope() as session:
            info = Dataset(
                space_id=space_id,
                bot_id=bot_id,
                collection_name=collection_name,
                user_id=user_id,
                description=description,
                embedding_model=embedding_model,
                permission=permission,
            )
            session.add(info)

    @staticmethod
    def get_dataset_by_space_id(space_id: str):
        with session_scope() as session:
            datasets = session.query(Dataset).filter(Dataset.space_id == space_id).all()
            return datasets

    @staticmethod
    def get_datasets_by_bot_id(bot_id: str):
        with session_scope() as session:
            datasets = session.query(Dataset).filter(Dataset.bot_id == bot_id).all()
            return datasets

    @staticmethod
    def get_spaces_by_collection_name(collection_name: str) -> list[Dataset]:
        with session_scope() as session:
            datasets = session.query(Dataset).filter(Dataset.collection_name == collection_name).all()
            return datasets

    @staticmethod
    def delete_dataset(space_id: str, bot_id: str, collection_name: str):
        with session_scope() as session:
            datasets = session.query(Dataset).filter(Dataset.space_id == space_id, Dataset.bot_id == bot_id).all()
            for dataset in datasets:
                if dataset.collection_name == collection_name:
                    session.delete(dataset)

    @staticmethod
    def get_all_datasets():
        with session_scope() as session:
            datasets = session.query(Dataset).all()
            return datasets

    @staticmethod
    def update_model_by_bot_id(bot_id: str, collection_name: str, embedding_model: str):
        with session_scope() as session:
            dataset = (
                session.query(Dataset)
                .filter(Dataset.bot_id == bot_id, Dataset.collection_name == collection_name)
                .one_or_none()
            )
            if dataset:
                dataset.embedding_model = embedding_model


class CollectionDB:
    @staticmethod
    def store_collection_info(
        user_id,
        knowledge_name,
        description,
        provider,
        embedding_model,
        similarity_threshold,
        index_params,
        chunk_size=FILE_SETTINGS["CHUNK_SIZE"],
        chunk_overlap=FILE_SETTINGS["CHUNK_OVERLAP"],
        top_k=FILE_SETTINGS["TOP_K"],
        folder="",
        knowledge_status=DOCUMENTSTATUS.WAITING.value,
    ) -> str:
        collection_name = f"c_{str(uuid.uuid4()).replace('-', '')}"
        with session_scope() as session:
            info = Knowledge(
                collection_name=collection_name,
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
                knowledge_status=knowledge_status,
            )
            session.add(info)
        return collection_name

    @staticmethod
    def store_tmp_collection_info(user_id, knowledge_name, description, embedding_model, index_params):
        with session_scope() as session:
            info = Knowledge(
                collection_name="temp",
                user_id=user_id,
                knowledge_name=knowledge_name,
                description=description,
                embedding_model=embedding_model,
                index_params=index_params,
            )
            session.add(info)

    @staticmethod
    def get_collection_by_user_id(user_id: str) -> list[Knowledge]:
        with session_scope() as session:
            collections = session.query(Knowledge).filter(Knowledge.user_id == user_id).all()
            return collections

    @staticmethod
    def get_all_db_collections() -> list[Knowledge]:
        with session_scope() as session:
            collections = session.query(Knowledge).all()
            return collections

    @staticmethod
    def drop_collection_by_name(collection_name: str):
        with session_scope() as session:
            collection = session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
            if collection:
                session.delete(collection)

    @staticmethod
    def get_collection_by_name(collection_name: str) -> Optional[Knowledge]:
        with session_scope() as session:
            collection = session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
            return collection

    @staticmethod
    def update_collection_field(collection_name: str):
        with session_scope() as session:
            collection = session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
            if collection:
                collection.update_at = datetime.now()

    @staticmethod
    def update_collection(
        collection_info: dict,
        knowledge_name: str,
        description: str,
        provider: str,
        embedding_model: str,
        embed_change: bool,
        similarity_threshold: float,
        dimension: int,
        chunk_size: int,
        chunk_overlap: int,
        top_k: int,
        folder: str,
    ):
        with session_scope() as session:
            collection_name = collection_info.get("collection_name", "")
            knowledge = session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
            if knowledge:
                knowledge.knowledge_name = knowledge_name
                knowledge.description = description
                knowledge.provider = provider
                knowledge.embedding_model = embedding_model
                knowledge.similarity_threshold = similarity_threshold
                knowledge.chunk_size = chunk_size
                knowledge.chunk_overlap = chunk_overlap
                knowledge.top_k = top_k
                if folder != knowledge.folder:
                    documents = session.query(Document).filter(Document.collection_name == collection_name).all()
                    for document in documents:
                        session.delete(document)
                    session.commit()

                knowledge.folder = folder
                knowledge.update_at = datetime.now()

                if embed_change:
                    if collection_name in [col.name for col in get_qdrant_client().get_collections().collections]:
                        get_qdrant_client().delete_collection(collection_name=collection_name)
                        logging.info(f"drop tmp collection {collection_name}")

                    index_params = collection_info.get("index_params", {})

                    # {'index_type': 'HNSW', 'metric_type': 'IP', 'params': {'M': 64, 'efConstruction': 512}}
                    hnsw_config = models.HnswConfigDiff(
                        m=index_params.get("params", {}).get("M", 64),
                        ef_construct=index_params.get("params", {}).get("efConstruction", 512),
                    )
                    vectors_config = models.VectorParams(
                        size=dimension,
                        datatype=models.Datatype.FLOAT16,
                        distance=models.Distance.COSINE,
                        hnsw_config=hnsw_config,
                    )
                    get_qdrant_client().create_collection(
                        collection_name=collection_name, vectors_config=vectors_config
                    )
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

                    documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
                    for document in documents:
                        PartitionDB.update_status(
                            partition_name=document.partition_name,
                            status=DOCUMENTSTATUS.WAITING.value,
                        )
                        PartitionDB.update_progress(partition_name=document.partition_name, progress=0.0)
            session.commit()

    @staticmethod
    def update_collection_status(collection_name: str, status: int, message: str = ""):
        with session_scope() as session:
            collection = session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
            if collection:
                collection.knowledge_status = status
                collection.message = message


class PartitionDB:
    @staticmethod
    def create_document(
        collection_name,
        file_id,
        file_name,
        file_url,
        file_type,
        description,
        progress,
        status=DOCUMENTSTATUS.WAITING.value,
        file_size=0,
    ) -> str:
        partition_name = f"d_{str(uuid.uuid4()).replace('-', '')}"
        with session_scope() as session:
            doc = Document(
                partition_name=partition_name,
                collection_name=collection_name,
                file_id=file_id,
                file_name=file_name,
                file_size=file_size,
                file_url=file_url,
                file_type=file_type,
                document_status=status,
                description=description,
                progress=progress,
            )
            session.add(doc)

            argo_tracking(DocumentTrackingPayload())
        return partition_name

    @staticmethod
    def drop_document(partition_name: str) -> str:
        with session_scope() as session:
            doc = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            if doc:
                session.delete(doc)
                return str(doc.file_id)
        return ""

    @staticmethod
    def get_document_site_count(file_id: str) -> int:
        with session_scope() as session:
            count = session.query(Document).filter(Document.file_id == file_id).count()
            return count

    @staticmethod
    def get_document_count(partition_name: str) -> int:
        try:
            with session_scope() as session:
                docs = session.query(Document).filter(Document.partition_name == partition_name).all()
                return len(docs)
        except Exception as ex:
            logging.exception(f"Failed to get document count for partition: {partition_name}")
            return -1

    @staticmethod
    def get_documents_by_collection_name(collection_name: str) -> list[Document]:
        with session_scope() as session:
            documents = session.query(Document).filter(Document.collection_name == collection_name).all()
            return documents

    @staticmethod
    def get_partition_by_partition_name(partition_name: str) -> Union[Document, None]:
        with session_scope() as session:
            document = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            return document

    @staticmethod
    def get_waiting_documents() -> Union[list[Document], None]:
        try:
            with session_scope() as session:
                documents = (
                    session.query(Document).filter(Document.document_status == DOCUMENTSTATUS.WAITING.value).all()
                )
                if documents is None:
                    return None
                documents = sorted(documents, key=lambda x: x.create_at)
                return documents
        except SQLAlchemyError as ex:
            logging.exception("Failed to fetch waiting documents")
            return None

    @staticmethod
    def update_progress(partition_name: str, progress: float):
        with session_scope() as session:
            document = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            if document:
                document.progress = progress

    @staticmethod
    def update_status(partition_name: str, status: int, msg: Optional[str] = ""):
        with session_scope() as session:
            document = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            if document:
                document.document_status = status
                if msg:
                    document.message = msg

    @staticmethod
    def update_content_info(partition_name: str, content: str, content_length: int):
        with session_scope() as session:
            document = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            if document:
                document.content = content
                document.content_length = content_length

    @staticmethod
    def get_document_by_file_id(file_id: str):
        with session_scope() as session:
            document = session.query(Document).filter(Document.file_id == file_id).first()
            return document

    @staticmethod
    def update_document_name(partition_name: str, file_name: str, file_size: int = 0):
        with session_scope() as session:
            document = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            if document:
                document.file_name = file_name
                if file_size:
                    document.file_size = file_size

    @staticmethod
    def update_description_name(partition_name: str, desc_name: str):
        with session_scope() as session:
            document = session.query(Document).filter(Document.partition_name == partition_name).one_or_none()
            if document:
                document.description = desc_name
