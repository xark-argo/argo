# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT
from typing import Optional

# from langgraph.prebuilt import create_react_agent
from core.agent.langgraph_agent.create_react_agent import create_react_agent
from core.agent.langgraph_agent.prompts.configuration import Configuration
from core.agent.langgraph_agent.prompts.template import apply_prompt_template
from core.agent.langgraph_agent.tools.tool_response_processor import create_tool_response_hook


# Create agents using configured LLM types
def create_agent(agent_name: str, llm, tools: list, prompt_template: str, configurable: Optional[Configuration] = None):
    """Factory function to create agents with consistent configuration."""

    tool_response_hook = create_tool_response_hook(
        max_tool_response_tokens=5000,  # 每个工具响应的最大token数
        summarization_model=llm,  # 用于摘要的模型
        # enable_chunking=True,
        # enable_summarization=True,
        enable_truncation=True,
    )

    return create_react_agent(
        name=agent_name,
        model=llm,
        tools=tools,
        prompt=lambda state: apply_prompt_template(prompt_template, state, configurable),
        pre_model_hook=tool_response_hook,  # 添加工具响应后,模型调用前的预处理hook
    )
