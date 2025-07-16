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
from core.agent.langgraph_agent.prompts.planner_model import Plan
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


def planner_node(state: State, config: RunnableConfig) -> Command[Literal["human_feedback", "reporter"]]:
    """Planner node that generate the full plan."""
    logger.info("Planner generating full plan")

    config_dict = config.get("configurable")
    if not config_dict:
        raise ValueError("System error: configurable is not found in config.")

    llm = config_dict.get("llm", None)
    configurable = Configuration.from_runnable_config(config)

    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    logging.info(f"Planner before apply_prompt_template: {plan_iterations}")
    messages = apply_prompt_template("planner", state, configurable)

    # logging.info(f"Planner apply_prompt_template: {messages}")

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

    llm = llm.with_structured_output(
        Plan,
        method="json_mode",
    )

    # if the plan iterations is greater than the max plan iterations, return the reporter node
    if plan_iterations >= configurable.max_plan_iterations:
        return Command(goto="reporter")

    logging.info(f"Planner messages: {messages}")
    full_response = ""
    response = llm.invoke(messages)
    if not response:
        raise ValueError("Planner llm response is None !!!")
        # return Command(goto="__end__")
    full_response = response.model_dump_json(indent=4, exclude_none=True)

    logger.info(f"Planner response: {full_response}")

    try:
        curr_plan = json.loads(repair_json_output(full_response))
    except json.JSONDecodeError:
        logging.warning("Planner response is not a valid JSON")
        if plan_iterations > 0:
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")
    if curr_plan.get("has_enough_context"):
        logging.info("Planner response has enough context.")
        new_plan = Plan.model_validate(curr_plan)
        return Command(
            update={
                "messages": [AIMessage(content=full_response, name="planner")],
                "current_plan": new_plan,
            },
            goto="reporter",
        )

    return Command(
        update={
            "messages": [AIMessage(content=full_response, name="planner")],
            "current_plan": full_response,
        },
        goto="human_feedback",
    )


def human_feedback_node(
    state: State,
    config: RunnableConfig,
) -> Command[Literal["planner", "research_team", "reporter", "__end__"]]:
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
        if new_plan["has_enough_context"]:
            goto = "reporter"
            return Command(
                update={
                    "current_plan": Plan.model_validate(new_plan),
                    "plan_iterations": plan_iterations,
                    "locale": new_plan["locale"],
                    "focus_info": focus_info,
                },
                goto=goto,
            )
    except json.JSONDecodeError:
        logging.warning("Planner response is not a valid JSON")
        if plan_iterations > 0:
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")

    # check if the plan is auto accepted
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

    return Command(
        update={
            "current_plan": Plan.model_validate(new_plan),
            "plan_iterations": plan_iterations,
            "locale": new_plan["locale"],
            "focus_info": focus_info,
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

    # Prepare the input for the agent with completed steps info
    agent_input = {
        "messages": [
            HumanMessage(
                content=f"{completed_steps_info}# Current Task\n\n## Title\n\n\
                {current_step.title}\n\n## Description\n\n\
                {current_step.description}\n\n## Locale\n\n\
                {state.get('locale', 'en-US')}"
            )
        ]
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
                # name="system", # If your agent handles HumanMessage with name="system" specifically
            )
        )

    # Invoke the agent
    default_recursion_limit = 30
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

    # logging.info(f"current_step: {current_step}")
    # logging.info(f"current_plan: {current_plan}")

    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=response_content,
                    name=agent_name,
                )
            ],
            "observations": observations + [response_content],
            "current_plan": current_plan,  # Save the updated plan back to state
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
