import logging
import operator
import os
from typing import Any

from qdrant_client import models

from core.file.file_db import FileDB
from core.model_providers import model_provider_manager
from database.db import session_scope
from database.vector import get_qdrant_client
from models import Knowledge


def get_embedding_function(provider: str, embedding_model: str):
    def model_embed(query):
        embedding = model_provider_manager.get_embedding_instance(provider, embedding_model)
        return embedding.embed_query(str(query))

    def generate_multiple(query, f):
        if isinstance(query, list):
            return [f(q) for q in query]
        else:
            return f(query)

    return lambda query: generate_multiple(query, model_embed)


def get_reranking_function(model_name: str):
    # Todo: add reranking function
    return None


def merge_and_sort_query_results(query_results, k, reverse=False):
    combined_distances: list[Any] = []
    combined_documents: list[Any] = []
    combined_metadatas: list[Any] = []

    for data in query_results:
        if data:
            combined_distances.extend(data["distances"])
            combined_documents.extend(data["documents"])
            combined_metadatas.extend(data["metadatas"])

    combined = list(zip(combined_distances, combined_documents, combined_metadatas))

    combined.sort(key=operator.itemgetter(0), reverse=reverse)

    if not combined:
        sorted_distances: list[Any] = []
        sorted_documents: list[Any] = []
        sorted_metadatas: list[Any] = []
    else:
        sorted_distances, sorted_documents, sorted_metadatas = [list(x) for x in zip(*combined)]
        sorted_distances = list(sorted_distances)[:k]
        sorted_documents = list(sorted_documents)[:k]
        sorted_metadatas = list(sorted_metadatas)[:k]

    result = {
        "distances": sorted_distances,
        "documents": sorted_documents,
        "metadatas": sorted_metadatas,
    }

    return result


def query_doc(
    collection_name: str,
    partition_names: list[str],
    query: str,
    provider: str,
    embedding_model: str,
    similarity_threshold: float,
    k: int,
    reranking_model,
    r: float,
):
    embedding_function = get_embedding_function(provider, embedding_model)

    vectors = embedding_function(query)
    if vectors is None:
        logging.error("query embedding error!")
        return {"distances": [], "documents": [], "metadatas": []}

    payloads = partition_names + ["page_content", "metadata"]
    result = get_qdrant_client().search(
        collection_name,
        query_vector=vectors,
        with_payload=models.PayloadSelectorInclude(include=payloads),
        with_vectors=True,
        score_threshold=similarity_threshold,
        limit=k,
    )

    reranking_function = get_reranking_function(reranking_model)
    if reranking_function:
        scores = reranking_function.predict([(query, each.payload.get("page_content", "")) for each in result])
    else:
        scores = [each.score for each in result]
    docs_with_scores = list(zip(result, scores))
    if r and r > 0:
        docs_with_scores = [(d, s) for d, s in docs_with_scores if s >= r]

    result = sorted(docs_with_scores, key=operator.itemgetter(1), reverse=True)
    distances = []
    documents = []
    metadatas = []
    for doc, doc_score in result[:k]:
        if doc_score < similarity_threshold:
            break
        metadata = doc.payload.get("metadata", {})
        metadata["score"] = doc_score
        distances.append(doc_score)
        documents.append(doc.payload.get("page_content", ""))
        metadatas.append(metadata)

    result = {
        "distances": distances,
        "documents": documents,
        "metadatas": metadatas,
    }
    # logging.info(f"query: {query}, query_doc result: {result}")
    return result


def get_search_context(table_info, prompt, provider, embedding_model, top_k, reranking_model, r):
    results = []
    context = ""
    content_list = []
    content_list.append("## Knowledge base information")
    for collection_name, documents in table_info.items():
        if collection_name == "temp":
            partition_names = []
            for document in documents:
                if document.content_length > 1000000:
                    partition_names.append(document.partition_name)
                else:
                    content_list.append(f"- **Source of information：{document.file_name}**")
                    content_list.append(f"> {document.content}")
                    content_list.append("\n")
        else:
            partition_names = [document.partition_name for document in documents]
        if partition_names:
            similarity_threshold = 0.0

            with session_scope() as session:
                cur_knowledge = (
                    session.query(Knowledge).filter(Knowledge.collection_name == collection_name).one_or_none()
                )

            if cur_knowledge:
                similarity_threshold = cur_knowledge.similarity_threshold
            result = query_doc(
                collection_name=collection_name,
                partition_names=partition_names,
                query=prompt,
                provider=provider,
                embedding_model=embedding_model,
                similarity_threshold=similarity_threshold,
                k=top_k,
                reranking_model=reranking_model,
                r=r,
            )
        else:
            result = {"distances": [], "documents": [], "metadatas": []}
        logging.info(
            f"query: {prompt}, partition_names: {[document.file_name for document in documents]}, result: {result}"
        )
        results.append(result)

    if context:
        logging.info(f"query: {prompt}, full_text_context: {context}")

    milvus_context = merge_and_sort_query_results(results, k=top_k, reverse=True)
    logging.info(f"query: {prompt}, top_k: {top_k}, milvus_search_context: {milvus_context}")

    context_string = ""
    citations = []
    if milvus_context:
        for i, document in enumerate(milvus_context["documents"]):
            source_file = milvus_context["metadatas"][i].get("source", "")
            try:
                source_file_id = os.path.basename(source_file)
                source_file_name = FileDB.get_file_by_id(file_id=source_file_id).file_name
            except Exception as ex:
                # if knowlege sync with folder, then it must except
                source_file_name = source_file_id

            content_list.append(f"- **Source of information：{source_file_name}**")
            content_list.append(f"> {document}")
            content_list.append("\n")

            citations.append(
                {
                    "source": source_file,
                    "source_file_name": source_file_name,
                    "document": document,
                    "metadata": milvus_context["metadatas"][i],
                }
            )
    if len(content_list) > 1:
        context = "\n".join(content_list)
    else:
        context = ""
    return context, citations
