from enum import Enum
from typing import Any, Optional, Union

from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel

from core.file.file_obj import FileVar


class ModelConfigEntity(BaseModel):
    """
    Model Config Entity.
    """

    provider: str
    model: str
    mode: str
    llm_instance: BaseLanguageModel
    parameters: dict[str, Any]
    stop: list[str]
    network: bool = False
    prologue: str = ""
    tool_config: list[dict[str, Union[str, list[str]]]]
    plugin_config: dict[str, Any]

    class Config:
        protected_namespaces = ()


class PromptTemplateEntity(BaseModel):
    """
    Prompt Template Entity.
    """

    class PromptType(Enum):
        """
        Prompt Type.
        'simple', 'advanced'
        """

        SIMPLE = "simple"
        ADVANCED = "advanced"

        @classmethod
        def value_of(cls, value: str) -> "PromptTemplateEntity.PromptType":
            """
            Get value of given mode.

            :param value: mode value
            :return: mode
            """
            for mode in cls:
                if mode.value == value:
                    return mode
            raise ValueError(f"invalid prompt type value {value}")

    prompt_type: PromptType
    simple_prompt_template: Optional[str] = None
    advanced_prompt_template: Optional[str] = None


class DatasetEntity(BaseModel):
    """
    Dataset Config Entity.
    """

    configs: dict[str, Any] = {}


class AgentToolEntity(BaseModel):
    """
    Agent Tool Entity.
    """

    tool_id: str
    config: dict[str, Any] = {}


class AgentPromptEntity(BaseModel):
    """
    Agent Prompt Entity.
    """

    first_prompt: str
    next_iteration: str


class PlanningStrategy(Enum):
    REACT = "react"
    REACT_DEEP_RESEARCH = "react_deep_research"
    REACT_DEEP_RESEARCH_AI_PRODUCT_MANAGER = "react_deep_research_ai_product_manager"
    REACT_ROUTER = "react_router"
    TOOL_CALL = "tool_call"


class AgentEntity(BaseModel):
    """
    Agent Entity.
    """

    provider: str
    model: str
    strategy: PlanningStrategy
    tools: list[AgentToolEntity]
    prompt: Optional[AgentPromptEntity] = None
    max_iteration: int = 25


class BotOrchestrationConfigEntity(BaseModel):
    """
    Bot Orchestration Config Entity.
    """

    bot_model_config: ModelConfigEntity
    prompt_template: PromptTemplateEntity
    agent: Optional[AgentEntity] = None

    # features
    dataset: Optional[DatasetEntity] = None


class InvokeFrom(Enum):
    """
    Invoke From.
    """

    SERVICE_API = "service-api"
    WEB_APP = "web-app"
    EXPLORE = "explore"
    DEBUGGER = "debugger"

    @classmethod
    def value_of(cls, value: str) -> "InvokeFrom":
        """
        Get value of given mode.

        :param value: mode value
        :return: mode
        """
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"invalid invoke from value {value}")

    def to_source(self) -> str:
        """
        Get source of invoke from.

        :return: source
        """
        if self == InvokeFrom.WEB_APP:
            return "web_app"
        elif self == InvokeFrom.DEBUGGER:
            return "dev"
        elif self == InvokeFrom.EXPLORE:
            return "explore_app"
        elif self == InvokeFrom.SERVICE_API:
            return "api"

        return "dev"


class ApplicationGenerateEntity(BaseModel):
    """
    Application Generate Entity.
    """

    task_id: str

    bot_id: str
    bot_category: str
    bot_name: str
    bot_model_config_id: str
    # for save
    bot_model_config_dict: dict

    # Converted from bot_model_config to Entity object, or directly covered by external input
    bot_orchestration_config_entity: BotOrchestrationConfigEntity

    conversation_id: Optional[str] = None
    regen_message_id: Optional[str] = None
    query: str
    inputs: dict[str, str]
    file_docs: list[str] = []
    files: list[dict] = []
    file_objs: list[FileVar] = []
    user_id: str
    # extras
    stream: bool
    invoke_from: InvokeFrom

    # extra parameters, like: auto_generate_conversation_name
    extras: dict[str, Any] = {}
