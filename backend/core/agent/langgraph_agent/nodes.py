# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import json
import logging
import os
import re
from typing import Annotated, Literal

from langchain.chains.summarize import load_summarize_chain
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.types import Command, interrupt

from core.agent.langgraph_agent.agents import create_agent
from core.agent.langgraph_agent.plan_manager import PlanManager
from core.agent.langgraph_agent.prompts.configuration import Configuration
from core.agent.langgraph_agent.prompts.planner_model import Plan, Step, StepType
from core.agent.langgraph_agent.prompts.template import apply_prompt_template
from core.agent.langgraph_agent.tools import (
    python_repl_tool,
)
from core.agent.langgraph_agent.types import State
from core.agent.langgraph_agent.utils.json_utils import repair_json_output
from core.i18n.translation import translation_loader

# from core.agent.langgraph_agent.tools.search import SELECTED_SEARCH_ENGINE, SearchEngine

logger = logging.getLogger(__name__)


def _get_node_config(state: State, config: RunnableConfig):
    """统一获取节点通用配置"""
    configurable = Configuration.from_runnable_config(config)
    config_dict = config.get("configurable", {})
    llm = config_dict.get("llm")
    tools = config_dict.get("tools", [])
    
    # 从可序列化数据恢复PlanManager
    plan_manager_data = state.get("plan_manager_data")
    plan_manager = None
    if plan_manager_data:
        plan_manager = PlanManager.from_dict(plan_manager_data)
    
    return {
        "state": state,
        "configurable": configurable,
        "config_dict": config_dict,
        "llm": llm,
        "tools": tools,
        "plan_manager": plan_manager
    }


def _convert_plan_manager_to_plan(plan_manager: PlanManager, locale: str = "zh-CN") -> Plan:
    """将PlanManager转换为兼容的Plan格式"""
    if not plan_manager or not plan_manager.nodes:
        return Plan(
            locale=locale,
            has_enough_context=False,
            thought="正在初始化DAG任务规划",
            title="DAG任务计划",
            steps=[]
        )
    
    snapshot = plan_manager.snapshot()
    nodes = snapshot['nodes']
    
    # 将DAG步骤转换为Step
    steps = []
    for step_id, step_data in nodes.items():
        # 跳过动态占位节点（它们的子节点会被包含）
        if step_data.get('dynamic', False):
            continue
            
        step = Step(
            title=step_data.get('title', step_id),
            description=step_data.get('thoughts', f"执行任务: {step_data.get('title', step_id)}"),
            step_type=StepType.RESEARCH if step_data.get('type') in ['research', 'fetch'] else StepType.PROCESSING,
            execution_res="done" if step_data.get('status') in ['done', 'skipped', 'failed'] else "",
            extra=step_data.get('extra')
        )
        steps.append(step)
    
    # 检查是否所有任务都已完成
    all_completed = all(step_data['status'] in ['done', 'skipped', 'failed'] for step_data in nodes.values())

    return Plan(
        locale=locale,
        has_enough_context=all_completed,
        thought=f"DAG任务执行中，当前有{len(steps)}个任务",
        title="DAG任务执行计划",
        steps=steps
    )








@tool
def handoff_to_planner(
    research_topic: Annotated[str, "The topic of the research task to be handed off."],
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
):
    """Handoff to planner agent to do plan."""
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to hand off to planner agent
    return

def planner_node(state: State, config: RunnableConfig) -> Command[Literal["research_team", "reporter"]]:
    """DAG任务规划节点"""
    
    logger.info("DAG planner generating plan")
    
    # 使用公共配置获取函数
    node_config = _get_node_config(state, config)
    llm = node_config["llm"]
    configurable = node_config["configurable"]
    plan_manager = node_config["plan_manager"]

    
    # 获取或初始化PlanManager
    if not plan_manager:
        plan_manager = PlanManager()
    
    plan_iterations = state.get("plan_iterations", 0)
    
    # 检查是否超过最大迭代次数
    if plan_iterations > configurable.max_plan_iterations:
        return Command(goto="reporter")

    # 判断规划模式
    user_goal = state.get("instruction", "") or state.get("research_topic", "")
    dag_snapshot = plan_manager.snapshot() if plan_manager.nodes else None
    expand_inputs = plan_manager.get_expand_inputs() if plan_manager.nodes else None
    
    # 构造DAG规划提示
    try:
        # 使用新的DAG提示词模板
        dag_context = {
            "USER_GOAL": user_goal,
            "DAG_SNAPSHOT": json.dumps(dag_snapshot, ensure_ascii=False, indent=2) if dag_snapshot else "",
            "EXPAND_INPUTS": json.dumps(expand_inputs, ensure_ascii=False, indent=2) if expand_inputs else "",
            "current_plan": state.get("current_plan", ""),
            "locale": state.get("locale", "zh-CN")
        }
        
        # 应用DAG提示词模板
        messages = apply_prompt_template("planner", {**state, **dag_context}, configurable)
        
        # 调用LLM生成规划
        response = llm.invoke(messages)
        full_response = response.content

        logger.info(f"DAG Planner response: {full_response[:500]}...")

        # 解析响应
        curr_update = json.loads(repair_json_output(full_response))
        
        # 验证响应格式
        if "add_nodes" not in curr_update:
            raise ValueError("Response missing 'add_nodes' field")
        
        # 应用更新到PlanManager
        if curr_update.get("add_nodes"):
            plan_manager.apply_update(curr_update)
            logger.info(f"Applied {len(curr_update['add_nodes'])} nodes to DAG")
        
        # 转换为Plan格式
        current_plan = _convert_plan_manager_to_plan(plan_manager, state.get("locale", "zh-CN"))
        
        # 更新状态
        return Command(
            update={
                "plan_manager_data": plan_manager.to_dict(),
                "current_plan": current_plan,
                "plan_iterations": plan_iterations + 1
            },
            goto="research_team"
        )
        
    except Exception as e:
        logger.error(f"DAG planning failed: {str(e)}")
        # 如果DAG规划失败，返回reporter结束流程
        return Command(goto="reporter")





def human_feedback_node(
    state: State,
    config: RunnableConfig,
) -> Command[Literal["planner", "research_team", "reporter", "__end__"]]:
    """Backward compatibility: auto-accept plan without user interaction."""
    current_plan = state.get("current_plan", "")

    # if the plan is accepted, run the following node
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    goto = "research_team"
    try:
        current_plan = repair_json_output(current_plan)
        # increment the plan iterations
        plan_iterations += 1
        # parse the plan
        new_plan = json.loads(current_plan)
        if new_plan.get("has_enough_context"):
            goto = "reporter"
            return Command(
                update={
                    "current_plan": Plan.model_validate(new_plan),
                    "plan_iterations": plan_iterations,
                    "locale": new_plan.get("locale", state.get("locale", "en-US"))
                },
                goto=goto,
            )
    except json.JSONDecodeError:
        logging.warning("Planner response is not a valid JSON")
        if plan_iterations > 0:
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")

    # Conditionally request human review when auto_accepted_plan is disabled
    auto_accepted_plan = state.get("auto_accepted_plan", False)
    if not auto_accepted_plan:
        logging.info(f"human_feedback_node current_plan: {current_plan}")
        feedback = interrupt("Please Review the Plan.")

        # if the feedback is not accepted, return the planner node
        edit_plan_str = f"[{translation_loader.translation.t('chat.edit_plan')}]".upper()
        accept_str = f"[{translation_loader.translation.t('chat.accepted')}]".upper()
        if feedback and str(feedback).upper().startswith(edit_plan_str):
            logging.info(f"human_feedback_node feedback: {feedback}")
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=feedback, name="feedback"),
                    ],
                },
                goto="planner",
            )
        elif feedback and str(feedback).upper().startswith(accept_str):
            logger.info("Plan is accepted by user.")
        else:
            raise TypeError(f"Interrupt value of {feedback} is not supported.")

    # Always auto-accept by default (when auto_accepted_plan=True)
    return Command(
        update={
            "current_plan": Plan.model_validate(new_plan),
            "plan_iterations": plan_iterations,
            "locale": new_plan.get("locale", state.get("locale", "en-US"))
        },
        goto=goto,
    )


def coordinator_node(state: State, config: RunnableConfig) -> Command[Literal["planner", "__end__"]]:
    # ) -> Command[Literal["planner", "background_investigator", "__end__"]]:
    """Coordinator node that communicate with customers."""
    
    # 使用公共配置获取函数
    node_config = _get_node_config(state, config)
    llm = node_config["llm"]
    configurable = node_config["configurable"]


    # logging.info(f"Coordinator state: {state}")

    messages = apply_prompt_template("coordinator", state)
    response = llm.bind_tools([handoff_to_planner]).invoke(messages)
    # logging.info(f"llm prompt[Coordinator]: {messages}, response: {response}")

    goto = "__end__"
    locale = state.get("locale", "en-US")  # Default locale if not specified
    research_topic = state.get("research_topic", "")

    if len(response.tool_calls) > 0:
        goto = "planner"
        if state.get("enable_background_investigation"):
            # if the search_before_planning is True, add the web search tool to the planner agent
            goto = "background_investigator"
        try:
            for tool_call in response.tool_calls:
                if tool_call.get("name", "") != "handoff_to_planner":
                    continue
                if tool_call.get("args", {}).get("locale") and tool_call.get("args", {}).get("research_topic"):
                    locale = tool_call.get("args", {}).get("locale")
                    research_topic = tool_call.get("args", {}).get("research_topic")
                    break
        except Exception as e:
            logging.exception("Error processing tool calls")
    else:
        logging.warning("Coordinator response contains no tool calls. Terminating workflow execution.")
        logging.debug(f"Coordinator response: {response}")

    if goto == "__end__":
        return Command(
            update={
                "messages": [AIMessage(content=response.content, name="coordinator")],
            },
            goto="__end__",
        )

    return Command(
        update={
            "locale": locale,
            "research_topic": research_topic,
            "resources": configurable.resources,
        },
        goto=goto,
    )


# def reporter_node(state: State, config: RunnableConfig):
async def reporter_node(state: State, config: RunnableConfig):
    """Reporter node that write a final report."""
    logging.info(f"Reporter write final report")
    
    # 使用公共配置获取函数
    node_config = _get_node_config(state, config)
    llm = node_config["llm"]
    configurable = node_config["configurable"]
    plan_manager = node_config["plan_manager"]

    invoke_messages = apply_prompt_template("reporter", state, configurable)
    # 获取所有已完成任务的观测结果
    observations = plan_manager.get_observations()
    logger.info(f"Retrieved {len(observations)} observations from plan_manager")

    if len(invoke_messages) > 0:
        # use only system prompt for reporter
        invoke_messages = [invoke_messages[0]]
    
    # add observations to invoke_messages
    # plan_manager返回的是字典格式 {task_id: observation}
    for task_id, observation in observations.items():
        # 提取观测结果的文本内容
        content = str(observation)
        
        invoke_messages.append(
            HumanMessage(
                content=f"Below are findings from task '{task_id}':\n\n{content}\n\n",
                name="observation",
            )
        )
    logging.info(f"Reporter node current invoke messages: {invoke_messages}")

    # response = llm.invoke(invoke_messages)
    # response_content = response.content
    # Use async streaming for better user experience in complex tasks
    response = await llm.ainvoke(invoke_messages)
    response_content = response.content

    logging.info(f"reporter response: {response_content}")

    return Command(
        update={
            "messages": [AIMessage(content=response_content, name="reporter")],
        },
        goto="__end__",
    )
    # return {"final_report": response_content}


async def research_team_node(state: State, config: RunnableConfig) -> Command[Literal["planner", "research_team", "reporter"]]:
    """Research team node that manages DAG task execution and dynamic expansion."""
    
    logger.info("Research team is managing DAG task execution.")
    
    # 防止无限循环：检查是否有循环计数器
    research_team_iterations = state.get("research_team_iterations", 0)
    max_iterations = 100  # 最大迭代次数
    
    if research_team_iterations >= max_iterations:
        logger.warning(f"Research team reached max iterations ({max_iterations}), proceeding to reporter")
        return Command(goto="reporter")
    
    # 使用公共配置获取函数
    node_config = _get_node_config(state, config)
    plan_manager = node_config["plan_manager"]
    
    # 初始化或获取PlanManager
    if not plan_manager:
        plan_manager = PlanManager()
        
    # 处理动态任务扩展
    dynamic_tasks = plan_manager.ready_dynamic_nodes()
    if dynamic_tasks:
        logger.info(f"Processing {len(dynamic_tasks)} dynamic tasks for expansion")
        # 只更新plan_manager_data，让planner负责更新current_plan
        return Command(
            update={
                "plan_manager_data": plan_manager.to_dict(),
                "research_team_iterations": research_team_iterations + 1
            },
            goto="planner"
        )
    
    # 检查并处理被阻塞的任务
    blocked_count = plan_manager.mark_blocked_as_skipped()
    if blocked_count > 0:
        logger.info(f"Marked {blocked_count} blocked tasks as skipped")

    # 转换为Plan格式
    current_plan = _convert_plan_manager_to_plan(plan_manager, state.get("locale", "zh-CN"))

    # 获取就绪的任务
    ready_tasks = plan_manager.ready_nodes()
    if not ready_tasks:
        # 既没有动态任务需要扩展，也没有就绪任务可以执行
        # 这意味着所有可执行的工作都已完成，应该进入报告阶段
        logger.info("No ready tasks and no dynamic tasks to expand, all work completed")

        return Command(
            update={
                "plan_manager_data": plan_manager.to_dict(),
                "current_plan": current_plan,
                "research_team_iterations": research_team_iterations + 1
            },
            goto="reporter"
        )
    
    # 选择要执行的任务并传递给researcher
    parallel_limit = state.get("parallel_execution_limit", 3)
    tasks_to_execute = ready_tasks[:parallel_limit]
    
    logger.info(f"Delegating {len(tasks_to_execute)} tasks to researcher: {tasks_to_execute}")
    
    # 只传递必要的状态，避免current_plan并发冲突
    return Command(
        update={
            "plan_manager_data": plan_manager.to_dict(),
            "current_plan": current_plan,
            "current_executing_tasks": tasks_to_execute,  # 传递给researcher_node执行
            "research_team_iterations": research_team_iterations + 1
        },
        goto="researcher"
    )


async def researcher_node(state: State, config: RunnableConfig) -> Command[Literal["research_team"]]:
    """研究员节点 - 负责并发执行多个任务，合并结果，统一返回"""

    # 使用公共配置获取函数
    node_config = _get_node_config(state, config)
    llm = node_config["llm"]
    tools = node_config["tools"]
    configurable = node_config["configurable"]
    plan_manager = node_config["plan_manager"]

    # Get instruction from state and add it to configurable
    instruction = state.get("instruction", "")
    locale = state.get("locale", "zh-CN")
    if instruction:
        configurable.instruction = instruction
    if locale:
        configurable.locale = locale

    # 获取要执行的任务
    current_executing_tasks = state.get("current_executing_tasks", [])
    
    if not plan_manager:
        logger.warning("No plan_manager found, ending workflow")
        return Command(goto="__end__")
    
    if not current_executing_tasks:
        logger.warning("No current_executing_tasks found, returning to research_team")
        return Command(goto="research_team")
    
    logger.info(f"Researcher executing {len(current_executing_tasks)} tasks concurrently: {current_executing_tasks}")
    
    # 并发执行多个任务
    task_results = await _execute_dag_tasks_parallel(
        plan_manager, current_executing_tasks, node_config
    )
    
    # 批量更新所有任务结果到plan_manager（在内存中完成，不触发状态更新）
    logger.info(f"researcher node plan_manager: {plan_manager.to_dict()}")
    for task_id, result in task_results.items():
        plan_manager.update_observation(task_id, result)
        status = result.get('status', 'unknown')
        if status == 'failed':
            logger.error(f"Task {task_id} failed: {result.get('error', 'Unknown error')}")
        else:
            logger.info(f"Task {task_id} completed successfully: {result.get('output', 'No output')}")
    logger.info(f"researcher node plan_manager update: {plan_manager.to_dict()}")
    # 一次性返回更新的状态，避免并发冲突
    return Command(
        update={
            "plan_manager_data": plan_manager.to_dict(),  # 包含所有任务结果的更新后的plan_manager
        },
        goto="research_team"
    )


async def _execute_dag_tasks_parallel(plan_manager: PlanManager, task_ids: list, node_config: dict):
    """并行执行多个DAG任务"""
    
    async def execute_single_task(task_id: str):
        """执行单个任务"""
        try:
            # 获取任务信息和输入
            snapshot = plan_manager.snapshot()
            task_node = snapshot['nodes'][task_id]
            task_inputs = plan_manager.execution_inputs(task_id)
            
            logger.info(f"Executing task {task_id}:{task_node['title']}, inputs: {task_inputs}")

            # 构造基于researcher模板的任务提示
            task_inputs_text = f"前序输入数据: \n{task_inputs}\n\n" if task_inputs else ""
            prompt = f"""
{task_inputs_text}
请执行以下任务并返回结果:
    任务ID: {task_id}
    任务标题: {task_node['title']}
    任务类型: {task_node['type']}
    执行思路: {task_node['thoughts']}

    请根据上述任务信息，执行具体的研究或分析工作。

"""
            # prompt = f"""
            #     请执行以下任务并返回结果:\n\n 
            #         任务ID: {task_id}
            #         任务标题: {task_node['title']}
            #         任务类型: {task_node['type']}
            #         执行思路: {task_node['thoughts']}

            #         请根据上述任务信息，执行具体的研究或分析工作。确保：
            #         1. 严格按照任务思路和目标执行
            #         2. 充分利用可用工具获取信息
            #         3. 完整保留原文内容和数据
            #         4. 返回结构化的研究结果
            #         5. 包含必要的引用和来源

            #         {f"前序输入数据: {task_inputs}" if task_inputs else ""}
            #     """
            
            # 直接构造消息，不使用apply_prompt_template（agent内部会处理）
            messages = [HumanMessage(content=prompt, name="researcher")]

            # 创建agent并执行
            agent = create_agent("researcher", node_config["llm"], node_config["tools"], "researcher", node_config["configurable"])
            
            # 执行agent - 传递正确的状态格式
            agent_state = {
                "messages": messages,
                "remaining_steps": 20,
            }
            result = await agent.ainvoke(agent_state, config={"recursion_limit":30})

            # 提取结果
            if 'messages' in result and result['messages']:
                last_message = result['messages'][-1]
                if hasattr(last_message, 'content'):
                    content = last_message.content
                else:
                    content = str(last_message)
            else:
                content = str(result)

            # 构造返回结果
            return {
                "task_id": task_id,
                "task_type": task_node['type'],
                "status": "done",
                "output": content
            }
            
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {str(e)}")
            return {
                "task_id": task_id,
                "task_type": task_node['type'],
                "status": "failed",
                "error": str(e),
                "output": f"任务执行失败: {str(e)}"
            }
    
    # 并行执行所有任务
    logger.info(f"Starting parallel execution of {len(task_ids)} tasks")
    results = await asyncio.gather(*[execute_single_task(task_id) for task_id in task_ids])
    
    # 转换为字典格式
    return {result["task_id"]: result for result in results}


async def coder_node(state: State, config: RunnableConfig) -> Command[Literal["research_team"]]:
    """Coder node that do code analysis - simplified for DAG mode."""
    logger.info("Coder node called - returning to research_team for DAG handling")
    
    # 在DAG模式下，coding任务也通过research_team_node统一管理
    return Command(goto="research_team")
