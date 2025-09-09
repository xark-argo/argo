# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.agent.langgraph_agent import nodes
from core.agent.langgraph_agent.prompts.planner_model import StepType
from core.agent.langgraph_agent.plan_manager import PlanManager

from .types import State

# import core.agent.langgraph_agent.nodes_ai_product_manager as nodes_ai_product_manager
# from .nodes import (
#     coordinator_node,
#     planner_node,
#     reporter_node,
#     research_team_node,
#     researcher_node,
#     coder_node,
#     human_feedback_node,
#     # background_investigation_node,
# )


# 已移除 continue_to_running_research_team 函数
# research_team_node 内部已经处理了所有路由逻辑


def _build_base_graph():
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", nodes.coordinator_node)
    # builder.add_node("background_investigator", background_investigation_node)
    builder.add_node("planner", nodes.planner_node)
    builder.add_node("reporter", nodes.reporter_node)
    builder.add_node("research_team", nodes.research_team_node)
    builder.add_node("researcher", nodes.researcher_node)
    builder.add_node("coder", nodes.coder_node)
    builder.add_node("human_feedback", nodes.human_feedback_node)
    # builder.add_edge("background_investigator", "planner")
    # research_team_node 内部已经处理了所有路由逻辑，不需要条件边
    # builder.add_conditional_edges(
    #     "research_team",
    #     continue_to_running_research_team,
    #     ["planner", "researcher", "coder", "research_team", "reporter"],
    # )
    builder.add_edge("reporter", END)
    return builder


# def _build_ai_product_manager_graph():
#     """Build and return the base state graph with all nodes and edges."""
#     builder = StateGraph(State)
#     builder.add_edge(START, "coordinator")
#     builder.add_node("coordinator", nodes_ai_product_manager.coordinator_node)
#     # builder.add_node("background_investigator", background_investigation_node)
#     builder.add_node("planner", nodes_ai_product_manager.planner_node)
#     builder.add_node("reporter", nodes_ai_product_manager.reporter_node)
#     builder.add_node("research_team", nodes_ai_product_manager.research_team_node)
#     builder.add_node("researcher", nodes_ai_product_manager.researcher_node)
#     builder.add_node("coder", nodes_ai_product_manager.coder_node)
#     builder.add_node("human_feedback", nodes_ai_product_manager.human_feedback_node)
#     # builder.add_edge("background_investigator", "planner")
#     builder.add_conditional_edges(
#         "research_team",
#         continue_to_running_research_team,
#         ["planner", "researcher", "coder"],
#     )
#     builder.add_edge("reporter", END)
#     return builder


def build_graph_with_memory(graph_type: str):
    """Build and return the agent workflow graph with memory."""
    # use persistent memory to save conversation history
    # TODO: be compatible with SQLite / PostgreSQL
    memory = MemorySaver()

    # build state graph
    if graph_type == "base":
        builder = _build_base_graph()
    # elif graph_type == "ai_product_manager":
    #     builder = _build_ai_product_manager_graph()
    else:
        raise ValueError(f"Invalid graph type: {graph_type}")
    return builder.compile(checkpointer=memory)
