from typing import Optional

from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.tools import BaseTool

from core.agent.agent_executor import (
    AgentConfiguration,
    AgentExecutor,
    PlanningStrategy,
)
from core.callback_handler.index_tool_callback_handler import (
    DatasetIndexToolCallbackHandler,
)
from core.entities.application_entities import (
    DatasetEntity,
    InvokeFrom,
    ModelConfigEntity,
)
from core.features.knowledge_tool import KnowledgeSearchTool
from models.knowledge import get_collection_by_name


class DatasetRetrievalFeature:
    async def retrieve(
        self,
        model_config: ModelConfigEntity,
        dataset: DatasetEntity,
        query: str,
        invoke_from: InvokeFrom,
        hit_callback: Optional[DatasetIndexToolCallbackHandler] = None,
        memory: Optional[BaseChatMemory] = None,
    ) -> Optional[str]:
        planning_strategy = PlanningStrategy.REACT_ROUTER

        dataset_retriever_tools = self.to_dataset_retriever_tool(
            doc_map=dataset.configs,
            hit_callback=hit_callback,
        )

        if len(dataset_retriever_tools) == 0:
            return None

        agent_configuration = AgentConfiguration(
            strategy=planning_strategy,
            bot_model_config=model_config,
            tools=dataset_retriever_tools,
            memory=memory,
            callbacks=[hit_callback] if hit_callback else None,
            max_iterations=3,
            max_execution_time=400.0,
            early_stopping_method="generate",
        )

        agent_executor = AgentExecutor(agent_configuration)

        result = await agent_executor.run(query)

        return result.output

    def temp_run(self, database_docs: list[str], query: str) -> Optional[str]:
        dataset_retriever_tools = self.to_dataset_retriever_tool(
            doc_map={"temp": database_docs},
        )

        if len(dataset_retriever_tools) == 0:
            return None

        tool = next(iter(dataset_retriever_tools))
        return str(tool.run(tool_input={"query": query}))

    def to_dataset_retriever_tool(
        self,
        doc_map: dict[str, list[str]],
        hit_callback: Optional[DatasetIndexToolCallbackHandler] = None,
    ) -> list[BaseTool]:
        tools = []
        hit_callbacks = [hit_callback] if hit_callback else []
        for collection_name, partition_names in doc_map.items():
            knowledge = get_collection_by_name(collection_name=collection_name)
            if knowledge:
                tool = KnowledgeSearchTool.from_knowledge(collection_name, partition_names, hit_callbacks=hit_callbacks)
                if tool:
                    tools.append(tool)

        return tools
