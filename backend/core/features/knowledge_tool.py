import logging
from typing import Callable, Optional, Union

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field, ValidationError
from pydantic.v1 import ValidationError as ValidationErrorV1

from configs.settings import FILE_SETTINGS
from core.callback_handler.agent_async_callback_handler import (
    AgentAsyncCallbackHandler,
)
from core.callback_handler.index_tool_callback_handler import (
    DatasetIndexToolCallbackHandler,
)
from core.features.doc_search import get_search_context
from core.model_providers.constants import OLLAMA_PROVIDER
from models.document import DOCUMENTSTATUS, get_documents_by_collection_name, get_partition_by_partition_name
from models.knowledge import get_collection_by_name


def _handle_knowledge_error(error: ToolException) -> str:
    result = f"knowledge tool execute error: {error.args[0]}"
    return result


def _handle_validation_error(e: Union[ValidationError, ValidationErrorV1]) -> str:
    return str(e)


class KnowledgeSearchToolInput(BaseModel):
    query: Union[str] = Field(..., description="")


class KnowledgeSearchTool(BaseTool):
    name: str = "knowledge_search"
    description: str = "support local sensitive data search"
    r: float = 0
    collection_name: str
    partition_names: list[str]
    hit_callbacks: list[Union[AgentAsyncCallbackHandler, DatasetIndexToolCallbackHandler]]
    args_schema: type[BaseModel] = KnowledgeSearchToolInput
    # no type will consider is str not functional     handle_tool_error = _handle_knowledge_error
    handle_tool_error: Optional[Union[bool, str, Callable[[ToolException], str]]] = _handle_knowledge_error
    handle_validation_error: Optional[Union[bool, str, Callable[[Union[ValidationError, ValidationErrorV1]], str]]] = (
        _handle_validation_error
    )

    @classmethod
    def from_knowledge(cls, collection_name: str, partition_names: list[str], **kwargs):
        knowledge = get_collection_by_name(collection_name=collection_name)
        if not knowledge:
            return None

        instance = cls(
            collection_name=collection_name,
            partition_names=partition_names,
            name=f"knowledge_search_{knowledge.collection_name}",
            description=f"Support local sensitive data search. Description: {knowledge.description}",
            **kwargs,
        )

        instance.metadata = {
            "tool_type": "dataset",
            "knowledge_name": knowledge.knowledge_name,
            "collection_name": knowledge.collection_name,
        }

        return instance

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        return ""

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        try:
            for hit_callback in self.hit_callbacks:
                await hit_callback.on_query(query, self.metadata)

            table_info = {}
            knowledge = get_collection_by_name(collection_name=self.collection_name)
            if knowledge is None:
                return ""

            top_k = knowledge.top_k
            if not top_k:
                top_k = FILE_SETTINGS["TOP_K"]
            provider_name = knowledge.provider or OLLAMA_PROVIDER
            embedding_model = knowledge.embedding_model

            documents = []
            if len(self.partition_names) > 0:
                for partition_name in self.partition_names:
                    document = get_partition_by_partition_name(partition_name=partition_name)
                    if document and document.document_status == DOCUMENTSTATUS.FINISH.value:
                        documents.append(document)
                table_info[self.collection_name] = documents
            else:
                documents = get_documents_by_collection_name(collection_name=self.collection_name)
                documents = [
                    document for document in documents if document.document_status == DOCUMENTSTATUS.FINISH.value
                ]
            if len(documents) == 0:
                raise ToolException(f"knowledge: {knowledge.knowledge_name} has no document")
            table_info[self.collection_name] = documents
            context_string, citations = get_search_context(
                table_info, query, provider_name, embedding_model, top_k, None, self.r
            )

            if self.hit_callbacks:
                context_list = []
                resource_number = 1
                for citation in citations:
                    metadata = citation.get("metadata", {})
                    source = {
                        "position": resource_number,
                        "dataset_id": knowledge.collection_name,
                        "dataset_name": knowledge.knowledge_name,
                        "document_path": citation.get("source", ""),
                        "document_name": citation.get("source_file_name", ""),
                        "score": metadata.get("score", 0),
                        "start_index": metadata.get("start_index", 0),
                        "content": citation.get("document", ""),
                    }
                    context_list.append(source)
                    resource_number += 1

                if run_manager:
                    for hit_callback in self.hit_callbacks:
                        await hit_callback.return_retriever_resource_info(context_list, run_manager.run_id)

            return str(context_string)
        except Exception as ex:
            logging.exception("Knowledge tool error")
            raise ToolException(str(ex))
