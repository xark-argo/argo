import json
import logging
import re
import uuid

import requests
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import Html2TextTransformer
from qdrant_client import models
from tqdm import tqdm

from configs.env import ARGO_STORAGE_PATH_DOCUMENTS
from core.model_providers import model_provider_manager
from core.model_providers.constants import OLLAMA_PROVIDER
from database.vector import get_qdrant_client
from models.document import DOCUMENTSTATUS, Document
from services.doc.doc_db import CollectionDB, PartitionDB
from services.doc.milvus_op import DocCollectionOp


class RecursiveUrlLoader:
    def __init__(
        self,
        document: Document,
    ):
        try:
            hyper_param = json.loads(document.description)
        except Exception as ex:
            logging.exception(f"Failed to parse hyper_param from document {document.partition_name}.")
            PartitionDB.update_status(
                partition_name=document.partition_name,
                status=DOCUMENTSTATUS.FAIL.value,
                msg=str(ex),
            )
            return
        self.url = hyper_param.get("url")
        self.base_url = hyper_param.get("base_url")
        self.max_depth = hyper_param.get("max_depth", 1)
        self.partition_name = document.partition_name
        self.collection_name = document.collection_name
        self.visited: set[str] = set()
        self.thread_num = 5
        is_valid = self.check_url_valid()
        if not is_valid:
            logging.exception("invalid url")
            PartitionDB.update_status(
                partition_name=document.partition_name,
                status=DOCUMENTSTATUS.FAIL.value,
                msg="invalid url",
            )
            return

        knowledge = CollectionDB.get_collection_by_name(collection_name=document.collection_name)
        if knowledge:
            self.embedding_model = knowledge.embedding_model
            self.provider = knowledge.provider or OLLAMA_PROVIDER

        # TODO use rebuild index

        self.file_path = f"{ARGO_STORAGE_PATH_DOCUMENTS}/{document.file_id}"

    def check_url_valid(self):
        try:
            response = requests.get(self.url)
            if response.status_code // 100 != 2:
                return False
            response = requests.get(self.base_url)
            if response.status_code // 100 != 2:
                return False
            return True
        except requests.RequestException as ex:
            logging.exception("Request failed.")
            return False

    def parse_sub_pages(self, urls: list[str], depth: int):
        urls = list(set(urls))
        batch = []
        logging.info(f"current visit: {self.visited}")
        if depth > self.max_depth or len(urls) == 0:
            return
        for url in urls:
            if url in self.visited:
                continue
            batch.append(url)
            if len(batch) == self.thread_num:
                self.visited.update(batch)
                loader = AsyncChromiumLoader(batch)
                docs = loader.load()
                reg = re.compile(r'href="(.*?)"')
                html2text = Html2TextTransformer()
                docs_transformed = html2text.transform_documents(docs)
                yield docs_transformed

                sub_links: list[str] = []
                for index in range(len(batch)):
                    tmp_links = reg.findall(docs[index].page_content)
                    for sub_link in tmp_links:
                        if (
                            "#" in sub_link
                            or "css" in sub_link
                            or "js" in sub_link
                            or ".ico" in sub_link
                            or ".jpg" in sub_link
                            or ".png" in sub_link
                            or sub_link in self.visited
                        ):
                            continue
                        if sub_link.startswith("http") or sub_link.startswith("https"):
                            sub_links.append(sub_link)
                        else:
                            sub_links.append(f"{self.base_url}{sub_link}")
                batch = []
                sub_links = list(set(sub_links))
                for docs in self.parse_sub_pages(urls=sub_links, depth=depth + 1):
                    yield docs

        if len(batch) > 0:
            self.visited.update(batch)
            loader = AsyncChromiumLoader(batch)
            docs = loader.load()
            reg = re.compile(r'href="(.*?)"')
            html2text = Html2TextTransformer()
            docs_transformed = html2text.transform_documents(docs)
            yield docs_transformed

            sub_links = []
            for index, current_url in enumerate(batch):
                tmp_links = reg.findall(docs[index].page_content)
                for sub_link in tmp_links:
                    if (
                        "#" in sub_link
                        or "css" in sub_link
                        or "js" in sub_link
                        or ".ico" in sub_link
                        or ".jpg" in sub_link
                        or ".png" in sub_link
                        or sub_link in self.visited
                    ):
                        continue
                    if sub_link.startswith("http") or sub_link.startswith("https"):
                        sub_links.append(sub_link)
                    else:
                        sub_links.append(f"{self.base_url}{sub_link}")
            sub_links = list(set(sub_links))
            for docs in self.parse_sub_pages(urls=sub_links, depth=depth + 1):
                yield docs

    def upload(self):
        urls = [self.url]
        batch = []
        success = False

        embedding = model_provider_manager.get_embedding_instance(self.provider, self.embedding_model)

        with open(self.file_path, "a") as fp:
            with tqdm(
                total=0,
                initial=0,
                unit="B",
                unit_scale=True,
                desc="processing website",
                ascii=True,
                dynamic_ncols=True,
            ) as progress_bar:
                for docs in self.parse_sub_pages(urls, depth=0):
                    document_count = PartitionDB.get_document_count(partition_name=self.partition_name)
                    if document_count == 0:
                        return

                    for each_doc in docs:
                        vectors = embedding.embed_query(each_doc.page_content)

                        batch.append(
                            {
                                "page_content": each_doc.page_content[:1000],
                                "vector": vectors or [],
                                "metadata": each_doc.metadata,
                            }
                        )
                        fp.write(
                            json.dumps(
                                {
                                    "metadata": each_doc.metadata,
                                    "page_content": each_doc.page_content,
                                },
                                ensure_ascii=False,
                            )
                        )
                        fp.write("\n")
                    try:
                        if len(batch) > 0:
                            points = []
                            for item in batch:
                                payload = item.get("metadata", {})
                                payload = payload.update(
                                    {
                                        self.partition_name: "1",
                                        "page_content": item.get("page_content", ""),
                                    }
                                )
                                points.append(
                                    models.PointStruct(
                                        id=str(uuid.uuid4()),
                                        vector=item.get("vector"),
                                        payload=payload,
                                    )
                                )

                            get_qdrant_client().upsert(
                                collection_name=self.collection_name,
                                points=points,
                                wait=False,
                            )

                            success = True
                    except Exception as ex:
                        logging.exception("Failed to upsert points.")
                    progress_bar.update(len(batch))
                    progress = round(progress_bar.n / progress_bar.n, 2)
                    PartitionDB.update_progress(partition_name=self.partition_name, progress=progress)
                    batch = []
                progress_bar.update(len(batch))
                progress = 1.0
                PartitionDB.update_progress(partition_name=self.partition_name, progress=progress)

        if success:
            PartitionDB.update_status(partition_name=self.partition_name, status=DOCUMENTSTATUS.FINISH.value)
            DocCollectionOp.rebuild_index(self.collection_name)
            CollectionDB.update_collection_field(collection_name=self.collection_name)
        else:
            PartitionDB.update_status(
                partition_name=self.partition_name,
                status=DOCUMENTSTATUS.FAIL.value,
                msg="url content null",
            )
