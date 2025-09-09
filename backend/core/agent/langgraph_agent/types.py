# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Annotated

from core.agent.langgraph_agent.prompts.planner_model import Plan
from core.agent.langgraph_agent.plan_manager import PlanManager


class Resource(BaseModel):
    """
    Resource is a class that represents a resource.
    """

    uri: str = Field(..., description="The URI of the resource")
    title: str = Field(..., description="The title of the resource")
    description: str | None = Field("", description="The description of the resource")


class State(MessagesState):
    """State for the agent system, extends MessagesState with DAG task management."""

    # Runtime Variables
    locale: str = "en-US"
    research_topic: str = ""
    observations: list[str] = []
    resources: list[Resource] = []
    plan_iterations: int = 0
    current_plan: Annotated[Plan | str, lambda x, y: y if y is not None else x] = None
    final_report: str = ""
    auto_accepted_plan: bool = True
    enable_background_investigation: bool = True
    background_investigation_results: str = None
    instruction: str = ""  # user instruction
    
    # DAG Task Management
    plan_manager_data: Annotated[Optional[Dict[str, Any]], lambda x, y: y if y is not None else x] = None  # DAG任务管理器的可序列化数据
    current_executing_tasks: list[str] = []  # 当前正要执行的任务列表
    parallel_execution_limit: int = 3  # 并行执行任务数量限制
