# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import dataclasses
import logging
from datetime import datetime
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from langgraph.prebuilt.chat_agent_executor import AgentState

from core.agent.langgraph_agent.prompts.configuration import Configuration
from utils.path import app_path

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(app_path("resources/langgraph_prompts")),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str) -> str:
    """
    Load and return a prompt template using Jinja2.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)

    Returns:
        The template string with proper variable substitution syntax
    """
    try:
        template = env.get_template(f"{prompt_name}.md")
        return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")


def apply_prompt_template(prompt_name: str, state: AgentState, configurable: Optional[Configuration] = None) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }
    # logging.info(f"apply_prompt_template input state {prompt_name}: {state}, state_vars: {state_vars}")

    # Add configurable variables
    # logging.info(f"apply_prompt_template {prompt_name} configurable: {configurable}")
    if configurable:
        config_dict = dataclasses.asdict(configurable)
        # remove keys in config_dict if it is in state_vars,
        # so that the state_vars will not be updated by duplicated keys in config_dict
        key_to_remove = []
        for key, value in config_dict.items():
            if key in state_vars:
                key_to_remove.append(key)
        logging.info(f"apply_prompt_template {prompt_name} key_to_remove: {key_to_remove}")
        for key in key_to_remove:
            config_dict.pop(key)
        state_vars.update(config_dict)

    try:
        # logging.info(f"apply_prompt_template {prompt_name} state_vars: {state_vars}")
        template = env.get_template(f"{prompt_name}.md")
        # logging.info(f"apply_prompt_template {prompt_name} template: {template}")
        system_prompt = template.render(**state_vars)
        # logging.info(f"apply_prompt_template {prompt_name} system_prompt: {system_prompt}")
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
