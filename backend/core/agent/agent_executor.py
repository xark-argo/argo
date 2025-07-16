from typing import Optional

from langchain.agents import Agent
from langchain.agents import AgentExecutor as LCAgentExecutor
from langchain.callbacks.manager import Callbacks
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Extra

from core.agent.agent.structed_multi_dataset_router_agent import (
    StructuredMultiDatasetRouterAgent,
)
from core.agent.output_parser.structured_chat import (
    StructuredChatOutputParser,
)
from core.entities.application_entities import (
    ModelConfigEntity,
    PlanningStrategy,
)
from core.features.knowledge_tool import KnowledgeSearchTool
from core.memory.conversation_db_buffer_memory import (
    ConversationBufferDBMemory,
)


class AgentConfiguration(BaseModel):
    strategy: PlanningStrategy
    bot_model_config: ModelConfigEntity
    tools: list[BaseTool] = []
    memory: Optional[ConversationBufferDBMemory] = None
    instruction: Optional[str] = None
    callbacks: Callbacks = None
    max_iterations: int = 6
    max_execution_time: Optional[float] = None
    early_stopping_method: str = "generate"

    class Config:
        """Configuration for this pydantic object."""

        protected_namespaces = ()
        extra = Extra.forbid
        arbitrary_types_allowed = True


class AgentExecuteResult(BaseModel):
    strategy: PlanningStrategy
    output: Optional[str]
    configuration: AgentConfiguration


class AgentExecutor:
    def __init__(self, configuration: AgentConfiguration):
        self.configuration = configuration
        self.agent = self._init_agent()

    def _init_agent(self) -> Agent:
        if self.configuration.strategy == PlanningStrategy.REACT_ROUTER:
            self.configuration.tools = [t for t in self.configuration.tools if isinstance(t, KnowledgeSearchTool)]
            agent = StructuredMultiDatasetRouterAgent.from_llm_and_tools(
                tools=self.configuration.tools,
                output_parser=StructuredChatOutputParser(),
                llm=self.configuration.bot_model_config.llm_instance,
                verbose=True,
            )
        else:
            raise NotImplementedError(f"Unknown Agent Strategy: {self.configuration.strategy}")

        return agent

    async def run(self, query: str) -> AgentExecuteResult:
        agent_executor = LCAgentExecutor.from_agent_and_tools(
            agent=self.agent,
            tools=self.configuration.tools,
            memory=self.configuration.memory,
            max_iterations=self.configuration.max_iterations,
            max_execution_time=self.configuration.max_execution_time,
            early_stopping_method=self.configuration.early_stopping_method,
            handle_parsing_errors=True,
        )

        try:
            output = await agent_executor.arun(input=query, callbacks=self.configuration.callbacks)
        except Exception as e:
            raise e

        return AgentExecuteResult(
            output=output,
            strategy=self.configuration.strategy,
            configuration=self.configuration,
        )
