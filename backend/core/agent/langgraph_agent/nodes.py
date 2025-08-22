# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

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
from core.agent.langgraph_agent.prompts.configuration import Configuration
from core.agent.langgraph_agent.prompts.planner_model import Plan, Step
from core.agent.langgraph_agent.prompts.template import apply_prompt_template
from core.agent.langgraph_agent.tools import (
    python_repl_tool,
)
from core.agent.langgraph_agent.types import State
from core.agent.langgraph_agent.utils.json_utils import repair_json_output
from core.i18n.translation import translation_loader

# from core.agent.langgraph_agent.tools.search import SELECTED_SEARCH_ENGINE, SearchEngine

logger = logging.getLogger(__name__)


def remove_think_tags(content: str) -> str:
    """Remove only the <think> and </think> tags but keep the content inside."""
    # Remove only the opening and closing tags, keep the content
    content = re.sub(r"<think>", "", content)
    content = re.sub(r"</think>", "", content)
    return content.strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _generate_step_key(step) -> str:
    """Generate a unique key for a step using normalized title and description."""

    deal_str = step.title
    
    if hasattr(step, 'description') and step.description:
        deal_str += "|" + str(step.description)[:50]

    return _normalize_text(deal_str)


def _merge_plan(old_plan: Plan | None, proposed_plan: Plan) -> Plan:
    """Merge proposed_plan into old_plan.
    
    - Preserve execution_res from old steps when titles match (unless decomposed)
    - Order strictly follows proposed_plan (LLM-decided)
    - Any leftover steps from old_plan (not in proposed_plan) are appended at the end in their original order
    - Automatically detect decomposed steps and set execution_res to "<decomposed>"
    """
    if not old_plan:
        return proposed_plan

    # Build index from old steps for carry-over of execution results
    old_index: dict[str, Step] = {}
    for s in old_plan.steps:
        key = _generate_step_key(s)
        old_index[key] = s

    # Build merged steps strictly following proposed plan order
    merged_steps: list[Step] = []
    seen_keys: set[str] = set()

    # First, add all completed steps from old_plan to preserve their execution results
    for old_step in old_plan.steps:
        if getattr(old_step, "execution_res", None):
            merged_steps.append(old_step)
            key = _generate_step_key(old_step)
            seen_keys.add(key)

    # Then, process proposed_plan steps in order
    for proposed_step in proposed_plan.steps:
        key = _generate_step_key(proposed_step)
        
        if key in seen_keys:
            # Update existing completed step if it's marked as decomposed
            for existing_step in merged_steps:
                if _generate_step_key(existing_step) == key:
                    # Check if the step is marked as decomposed in either title or description
                    is_decomposed = (
                        (proposed_step.title and str(proposed_step.title).startswith("<decomposed>")) or
                        (proposed_step.description and str(proposed_step.description).startswith("<decomposed>"))
                    )
                    if is_decomposed:
                        existing_step.execution_res = "<decomposed>"
                        # Update description if it contains decomposed marker
                        if proposed_step.description and str(proposed_step.description).startswith("<decomposed>"):
                            existing_step.description = proposed_step.description
                        # Update title if it contains decomposed marker
                        if proposed_step.title and str(proposed_step.title).startswith("<decomposed>"):
                            existing_step.title = proposed_step.title
                    break
        else:
            # Add new step from proposed plan
            merged_step = proposed_step

            # If this is a decomposed marker, mark as completed with special token
            is_decomposed = (
                (merged_step.title and str(merged_step.title).startswith("<decomposed>")) or
                (merged_step.description and str(merged_step.description).startswith("<decomposed>"))
            )
            if is_decomposed:
                merged_step.execution_res = "<decomposed>"

            merged_steps.append(merged_step)
            seen_keys.add(key)

    # Append leftover old steps not present in proposed plan, preserving original order
    for old_step in old_plan.steps:
        key = _generate_step_key(old_step)
        if key not in seen_keys:
            merged_steps.append(old_step)

    return Plan(
        locale=proposed_plan.locale or old_plan.locale,
        has_enough_context=proposed_plan.has_enough_context,
        # 在replan时保留原有plan的thought，避免影响后续任务的执行
        thought=old_plan.thought if old_plan and old_plan.thought else proposed_plan.thought,
        title=old_plan.title if old_plan and old_plan.title else proposed_plan.title,
        steps=merged_steps,
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


# def background_investigation_node(
#     state: State, config: RunnableConfig
# ):
#     logger.info("background investigation node is running.")
#     configurable = Configuration.from_runnable_config(config)
#     query = state.get("research_topic")
#     background_investigation_results = None
#     if SELECTED_SEARCH_ENGINE == SearchEngine.TAVILY.value:
#         searched_content = LoggedTavilySearch(
#             max_results=configurable.max_search_results
#         ).invoke(query)
#         if isinstance(searched_content, list):
#             background_investigation_results = [
#                 f"## {elem['title']}\n\n{elem['content']}" for elem in searched_content
#             ]
#             return {
#                 "background_investigation_results": "\n\n".join(
#                     background_investigation_results
#                 )
#             }
#         else:
#             logger.error(
#                 f"Tavily search returned malformed response: {searched_content}"
#             )
#     else:
#         background_investigation_results = get_web_search_tool(
#             configurable.max_search_results
#         ).invoke(query)
#     return {
#         "background_investigation_results": json.dumps(
#             background_investigation_results, ensure_ascii=False
#         )
#     }


def planner_node(state: State, config: RunnableConfig) -> Command[Literal["research_team", "reporter"]]:
    """Planner node that generate or update the plan automatically without human confirmation."""
    logger.info("Planner generating plan (auto mode)")

    config_dict = config.get("configurable")
    if not config_dict:
        raise ValueError("System error: configurable is not found in config.")

    llm = config_dict.get("llm", None)
    configurable = Configuration.from_runnable_config(config)

    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    logging.info(f"Planner before apply_prompt_template: {plan_iterations}")
    messages = apply_prompt_template("planner", state, configurable)

    # Rebuild messages to avoid excessive context: keep only
    # - the initial input messages (historical user/assistant without workflow-specific names)
    # - the last tail message IF AND ONLY IF it's from research agents or feedback (by name check on the last element)
    try:
        system_prompt_msg = messages[0] if len(messages) > 0 else None
        # Extract initial input messages from state["messages"]
        initial_input_messages = []
        for m in state.get("messages", []):
            m_name = getattr(m, "name", None)
            if not m_name:  # keep messages without workflow-specific names
                initial_input_messages.append(m)
        # Only consider the very last message as the execution/feedback result
        last_feedback_message = None
        if state.get("messages", []):
            tail = state["messages"][-1]
            tail_name = getattr(tail, "name", None)
            if isinstance(tail_name, str) and ("researcher" in tail_name or "feedback" in tail_name):
                last_feedback_message = tail
        # Compose filtered messages for planner
        filtered_messages = []
        if system_prompt_msg is not None:
            filtered_messages.append(system_prompt_msg)
        filtered_messages.extend(initial_input_messages)
        if last_feedback_message is not None:
            filtered_messages.append(last_feedback_message)

        # Start from filtered_messages as the base
        messages = filtered_messages

        # Append sanitized current_plan summary (without execution_res content)
        try:
            current_plan = state.get("current_plan")
            sanitized_plan = None
            if current_plan:
                def _sanitize_plan(plan_obj):
                    try:
                        # Prefer object access if it's a pydantic model
                        steps = []
                        for s in getattr(plan_obj, "steps", []) or []:
                            steps.append(
                                {
                                    "title": getattr(s, "title", None),
                                    "description": getattr(s, "description", None),
                                    "step_type": getattr(s, "step_type", None),
                                    "need_search": getattr(s, "need_search", None),
                                    # Mark completion status only, do not include execution_res
                                    "status": "completed" if getattr(s, "execution_res", None) else "pending",
                                }
                            )
                        return {
                            "title": getattr(plan_obj, "title", None),
                            "thought": getattr(plan_obj, "thought", None),
                            "locale": getattr(plan_obj, "locale", state.get("locale", "en-US")),
                            "has_enough_context": getattr(plan_obj, "has_enough_context", None),
                            "steps": steps,
                        }
                    except Exception:
                        return None
                sanitized_plan = _sanitize_plan(current_plan)
                if not sanitized_plan and isinstance(current_plan, str):
                    try:
                        raw = json.loads(current_plan)
                        steps = []
                        for s in raw.get("steps", []) or []:
                            steps.append(
                                {
                                    "title": s.get("title"),
                                    "description": s.get("description"),
                                    "step_type": s.get("step_type"),
                                    "need_search": s.get("need_search"),
                                    "status": "completed" if s.get("execution_res") else "pending",
                                }
                            )
                        sanitized_plan = {
                            "title": raw.get("title"),
                            "thought": raw.get("thought"),
                            "locale": raw.get("locale", state.get("locale", "en-US")),
                            "has_enough_context": raw.get("has_enough_context"),
                            "steps": steps,
                        }
                    except Exception:
                        sanitized_plan = None
                if sanitized_plan:
                    messages.append(
                        {
                            "role": "assistant",
                            "name": "plan_context",
                            "content": "Current plan summary (execution results omitted):\n"
                            + json.dumps(sanitized_plan, ensure_ascii=False, indent=2),
                        }
                    )

                    # If there are pending steps that reference a collection size (e.g., "获取10个股票…")
                    # add a light-weight, regex-free guidance for LLM to decide decomposition
                    try:
                        has_pending = any(
                            (step.get("status") == "pending") for step in (sanitized_plan.get("steps", []) or [])
                        )
                        if has_pending:
                            hint = (
                                "If the most recent research finding produced a concrete entity list (e.g., specific tickers/URLs/names), "
                                "use your judgment to decide whether to replace any generic collection steps with multiple sub-steps, "
                                "each handling exactly ONE explicit entity (DO NOT GROUP). Keep steps precise and executable; avoid copying large texts."
                            )
                            messages.append(
                                {
                                    "role": "user",
                                    "name": "decompose_guidance",
                                    "content": hint,
                                }
                            )
                    except Exception:
                        logging.exception("Failed to add decomposition guidance; continue without it.")
        except Exception:
            logging.exception("Failed to append sanitized current_plan summary; skipping plan context.")
    except Exception:
        logging.exception("Failed to filter planner messages; falling back to full messages.")

    if state.get("enable_background_investigation") and state.get("background_investigation_results"):
        messages += [
            {
                "role": "user",
                "content": (
                    "background investigation results of user query:\n"
                    + state["background_investigation_results"]
                    + "\n"
                ),
            }
        ]

    llm = llm.with_structured_output(Plan, method="json_mode")

    # if the plan iterations is greater than the max plan iterations, return the reporter node
    if plan_iterations > configurable.max_plan_iterations:
        return Command(goto="reporter")

    logging.info(f"Planner messages: {messages}")
    response = llm.invoke(messages)
    if not response:
        raise ValueError("Planner llm response is None !!!")
    full_response = ""

    # 初始化merged_plan为old_plan
    old_plan = state.get("current_plan") if isinstance(state.get("current_plan"), Plan) else None
    merged_plan = old_plan

    try:
        full_response = response.model_dump_json(indent=4, exclude_none=True)

        logger.info(f"Planner response: {full_response}")

        curr_update = json.loads(repair_json_output(full_response))
        # JSON解析成功，尝试解析为Plan
        try:
            proposed_plan = Plan.model_validate(curr_update)
            # Plan验证成功，执行合并
            merged_plan = _merge_plan(old_plan, proposed_plan)
        except Exception as e:
            logging.warning(f"Failed to parse planner response as Plan: {e}")
            # Plan验证失败，merged_plan保持为old_plan
            pass
    except json.JSONDecodeError:
        logging.warning("Planner response is not a valid JSON")
        # JSON解析失败，merged_plan保持为old_plan
        pass

    # 检查merged_plan是否为空
    if not merged_plan:
        # 如果没有merged_plan，则根据迭代次数决定去向
        if plan_iterations > 0:
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")

    # _merge_plan automatically preserves execution_res from old_plan
    # No need for manual fills logic

    # Decide next hop by actual step completion, not only by has_enough_context
    steps = merged_plan.steps or []
    all_completed = len(steps) == 0 or all(getattr(s, "execution_res", None) for s in steps)
    if all_completed:
        logging.info("All steps completed or no steps remaining. Finishing to reporter.")
        return Command(
            update={
                "messages": [AIMessage(content=full_response, name="planner")],
                "current_plan": merged_plan,
                "should_replan": False,
            },
            goto="reporter",
        )

    # Pending steps remain: accept automatically and continue to research team
    plan_iterations += 1
    return Command(
        update={
            "messages": [AIMessage(content=full_response, name="planner")],
            "current_plan": merged_plan,
            "plan_iterations": plan_iterations,
            "should_replan": False,
        },
        goto="research_team",
    )


def human_feedback_node(
    state: State,
    config: RunnableConfig,
) -> Command[Literal["planner", "research_team", "reporter", "__end__"]]:
    """Backward compatibility: auto-accept plan without user interaction."""
    current_plan = state.get("current_plan", "")

    focus_info = {}

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
                    "locale": new_plan.get("locale", state.get("locale", "en-US")),
                    "focus_info": focus_info,
                    "should_replan": False,
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
            "locale": new_plan.get("locale", state.get("locale", "en-US")),
            "focus_info": focus_info,
            "should_replan": False,
        },
        goto=goto,
    )


def coordinator_node(state: State, config: RunnableConfig) -> Command[Literal["planner", "__end__"]]:
    # ) -> Command[Literal["planner", "background_investigator", "__end__"]]:
    """Coordinator node that communicate with customers."""
    configurable = Configuration.from_runnable_config(config)

    config_dict = config.get("configurable")
    if not config_dict:
        raise ValueError("System error: configurable is not found in config.")

    llm = config_dict.get("llm", None)

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
    logging.info(f"Reporter write final report, state: {state}")
    configurable = Configuration.from_runnable_config(config)

    # Get focus_info from state and add it to configurable
    focus_info = state.get("focus_info", {})
    if focus_info:
        configurable.focus_info = focus_info
        logging.info(f"Reporter node received focus_info from state: {focus_info}")

    llm = config.get("configurable").get("llm", None)

    invoke_messages = apply_prompt_template("reporter", state, configurable)
    observations = state.get("observations", [])

    if len(invoke_messages) > 0:
        # use only system prompt for reporter
        invoke_messages = [invoke_messages[0]]
    # add observations to invoke_messages
    for observation in observations:
        invoke_messages.append(
            HumanMessage(
                content=f"Below are some findings for the research task:\n\n{observation}\n\n",
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


def research_team_node(state: State):
    """Research team node that collaborates on tasks."""
    logging.info("Research team is collaborating on tasks.")
    pass


async def _summarize_if_too_long(content: str, llm, max_length: int) -> str:
    if len(content) <= max_length:
        return content

    logging.info(f"Content {content[:50]}... length {len(content)} exceeds max_length {max_length}. Summarizing...")
    doc = Document(page_content=content)
    try:
        summarize_chain = load_summarize_chain(llm, chain_type="map_reduce")
        summary_result = await summarize_chain.arun([doc])
        logging.info(f"Summarized content length: {len(summary_result)}")
        return summary_result
    except Exception as e:
        logging.exception(f"Error during summarization. Returning truncated original. Content {content[:50]}...")
        return content[:max_length] + "... (content truncated due to summarization error)"


async def _execute_agent_step(
    state: State, agent, agent_name: str, llm: BaseLanguageModel
) -> Command[Literal["research_team"]]:
    """Helper function to execute a step using the specified agent."""
    current_plan = state.get("current_plan")
    observations = state.get("observations", [])
    logging.info(f"_execute_agent_step, current_plan: {current_plan}, observations: {observations}")

    if not isinstance(current_plan, Plan):  # Basic type check
        logging.error("current_plan is not a Plan object or is missing.")
        # Decide how to handle this - maybe go to an error state or end.
        return Command(update={"error": "Plan missing"}, goto="research_team")  # Or some error node

    # Find the first unexecuted step
    current_step = None
    completed_steps = []
    for step in current_plan.steps:
        if not step.execution_res:
            current_step = step
            break
        else:
            completed_steps.append(step)

    if not current_step:
        logging.warning("No unexecuted step found")
        return Command(goto="research_team")

    logging.info(f"Executing step: {current_step.title}, agent: {agent_name}")

    # Format completed steps information
    completed_steps_info = ""
    if completed_steps:
        completed_steps_info = "# Existing Research Findings\n\n"
        for i, step in enumerate(completed_steps):
            completed_steps_info += f"## Existing Finding {i + 1}: {step.title}\n\n"
            completed_steps_info += f"<finding>\n{step.execution_res}\n</finding>\n\n"

    # Get the recursion limit from the environment variable
    default_recursion_limit = 25
    try:
        env_value_str = os.getenv("AGENT_RECURSION_LIMIT", str(default_recursion_limit))
        parsed_limit = int(env_value_str)

        if parsed_limit > 0:
            recursion_limit = parsed_limit
            logging.info(f"Recursion limit set to: {recursion_limit}")
        else:
            logging.warning(
                f"AGENT_RECURSION_LIMIT value '{env_value_str}' (parsed as {parsed_limit}) is not positive. "
                f"Using default value {default_recursion_limit}."
            )
            recursion_limit = default_recursion_limit
    except ValueError:
        raw_env_value = os.getenv("AGENT_RECURSION_LIMIT")
        logging.warning(
            f"Invalid AGENT_RECURSION_LIMIT value: '{raw_env_value}'. Using default value {default_recursion_limit}."
        )
        recursion_limit = default_recursion_limit

    # Prepare the input for the agent with completed steps info
    agent_input = {
        "messages": [
            HumanMessage(
                content=f"{completed_steps_info}# Current Task\n\n## Title\n\n\
                {current_step.title}\n\n## Description\n\n\
                {current_step.description}\n\n## Locale\n\n\
                {state.get('locale', 'en-US')}"
            )
        ],
        "remaining_steps": recursion_limit  # 传递剩余步骤数
    }

    # Add citation reminder for researcher agent
    if agent_name.startswith("researcher"):
        if state.get("resources"):
            resources_info = "**The user mentioned the following resource files:**\n\n"
            for resource in state.get("resources"):
                resources_info += f"- {resource.title} ({resource.description})\n"

            agent_input["messages"].append(
                HumanMessage(
                    content=resources_info
                    + "\n\n"
                    + "You MUST use the **knowledge_search** to retrieve the information from the resource files.",
                )
            )

        agent_input["messages"].append(
            HumanMessage(
                content="IMPORTANT: DO NOT include inline citations in the text. \
                    Instead, track all sources and include a References section \
                        at the end using link reference format. \
                    Include an empty line between each citation for better readability. \
                    Use this format for each reference:\n\
                        - [Source Title](URL)\n\n- [Another Source](URL). \
                    If you got the same information from the same tool, you can skip the same tool call.",
            )
        )

    # Invoke the agent
    logging.info(f"Agent[{agent_name}] input: {agent_input}")
    result = await agent.ainvoke(input=agent_input, config={"recursion_limit": recursion_limit})

    # Process the result
    response_content = result["messages"][-1].content
    logging.info(f"Agent[{agent_name}] input response: {len(response_content)}, {response_content[0:50]}...")

    # Summarize if too long, especially for the researcher
    if agent_name.startswith("researcher"):  # Or any agent prone to long outputs
        response_content = await _summarize_if_too_long(response_content, llm, 5000)

    # Update the step with the execution result
    current_step.execution_res = response_content
    logging.info(f"Step '{current_step.title}' execution completed by {agent_name}")

    return Command(
        update={
            "messages": [
                AIMessage(
                    content=response_content,
                    name=agent_name,
                )
            ],
            "observations": observations + [response_content],
            "current_plan": current_plan,  # Save the updated plan back to state
            "should_replan": True,
        },
        goto="research_team",
    )


async def _setup_and_execute_agent_step(
    state: State, agent_type: str, llm, tools: list[BaseTool], config: Configuration = None
) -> Command[Literal["research_team"]]:
    # Use default tools if no MCP servers are configured
    agent = create_agent(agent_type, llm, tools, agent_type, config)
    return await _execute_agent_step(state, agent, agent_type, llm)


async def researcher_node(state: State, config: RunnableConfig) -> Command[Literal["research_team"]]:
    """Researcher node that do research"""
    configurable = Configuration.from_runnable_config(config)

    # Get focus_info from state and add it to configurable
    focus_info = state.get("focus_info", {})
    if focus_info:
        configurable.focus_info = focus_info
        logger.info(f"Researcher node received focus_info from state: {focus_info}")

    # Get instruction from state and add it to configurable
    instruction = state.get("instruction", "")
    if instruction:
        configurable.instruction = instruction

    # logger.info(f"Researcher node is researching, state: {state}, config: {config}, configurable: {configurable}")

    config_dict = config.get("configurable")
    if not config_dict:
        raise ValueError("System error: configurable is not found in config.")

    llm = config_dict.get("llm", None)
    tools = config_dict.get("tools", None)
    logging.info(f"Researcher tools: {tools}")
    return await _setup_and_execute_agent_step(
        state=state,
        agent_type="researcher",
        llm=llm,
        tools=tools,
        config=configurable,
    )


async def coder_node(state: State, config: RunnableConfig) -> Command[Literal["research_team"]]:
    """Coder node that do code analysis."""
    configurable = Configuration.from_runnable_config(config)

    # Get focus_info from state and add it to configurable
    focus_info = state.get("focus_info", {})
    if focus_info:
        configurable.focus_info = focus_info
        logger.info(f"Coder node received focus_info from state: {focus_info}")

    config_dict = config.get("configurable")
    if not config_dict:
        raise ValueError("System error: configurable is not found in config.")

    llm = config_dict.get("llm", None)

    return await _setup_and_execute_agent_step(
        state,
        agent_type="researcher_coder",
        llm=llm,
        tools=[python_repl_tool],
        config=configurable,
    )
