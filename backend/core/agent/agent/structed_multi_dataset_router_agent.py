import re
import uuid
from collections.abc import Sequence
from typing import Any, Optional, Union

from langchain.agents import Agent, AgentOutputParser, StructuredChatAgent
from langchain.agents.structured_chat.base import HUMAN_MESSAGE_TEMPLATE
from langchain.agents.structured_chat.prompt import PREFIX, SUFFIX
from langchain.callbacks.manager import Callbacks
from langchain.chains.llm import LLMChain
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import BaseCallbackManager
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import ToolMessage
from langchain_core.prompts import (
    BasePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.tools import BaseTool

FORMAT_INSTRUCTIONS = """Use a json blob to specify a tool by providing an action key (tool name) and an \
action_input key (tool input).
The nouns in the format of "Thought", "Action", "Action Input", "Final Answer" must be expressed in English.
Valid "action" values: "Final Answer" or {tool_names}

Provide only ONE action per $JSON_BLOB, as shown:

```
{{{{
  "action": $TOOL_NAME,
  "action_input": $INPUT
}}}}
```

Follow this format:

Question: input question to answer
Thought: consider previous and subsequent steps
Action:
```
$JSON_BLOB
```
Observation: action result
... (repeat Thought/Action/Observation N times)
Thought: I know what to respond
Action:
```
{{{{
  "action": "Final Answer",
  "action_input": "Final response to human"
}}}}
```"""


class StructuredMultiDatasetRouterAgent(StructuredChatAgent):
    dataset_tools: Sequence[BaseTool]
    tool_call_id: str = str(uuid.uuid4())

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    async def aplan(
        self,
        intermediate_steps: list[tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[AgentAction, AgentFinish]:
        """Given input, decided what to do.

        Args:
            intermediate_steps: Steps the LLM has taken to date,
                along with observations
            callbacks: Callbacks to run.
            **kwargs: User inputs.

        Returns:
            Action specifying what tool to use.
        """
        if len(self.dataset_tools) == 0:
            return AgentFinish(return_values={"output": ""}, log="")
        elif len(self.dataset_tools) == 1:
            tool = next(iter(self.dataset_tools))
            rst = await tool.arun(
                tool_input={"query": kwargs["input"]}, callbacks=callbacks, tool_call_id=self.tool_call_id
            )
            output = str(rst.content) if isinstance(rst, ToolMessage) else rst
            return AgentFinish(return_values={"output": output}, log=output)

        if intermediate_steps:
            _, observation = intermediate_steps[-1]
            return AgentFinish(return_values={"output": observation}, log=observation)

        full_inputs = self.get_full_inputs(intermediate_steps, **kwargs)

        try:
            full_output = self.llm_chain.predict(callbacks=callbacks, **full_inputs)
        except Exception as e:
            raise e

        try:
            agent_decision = self.output_parser.parse(full_output)
            if isinstance(agent_decision, AgentAction):
                tool_inputs = agent_decision.tool_input
                if isinstance(tool_inputs, dict) and "query" in tool_inputs:
                    tool_inputs["query"] = kwargs["input"]
                    agent_decision.tool_input = tool_inputs
                elif isinstance(tool_inputs, str):
                    agent_decision.tool_input = kwargs["input"]
            else:
                agent_decision.return_values["output"] = ""
            return agent_decision
        except OutputParserException:
            return AgentFinish(
                {"output": "I'm sorry, the answer of model is invalid, I don't know how to respond to that."},
                "",
            )

    @classmethod
    def create_prompt(
        cls,
        tools: Sequence[BaseTool],
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        human_message_template: str = HUMAN_MESSAGE_TEMPLATE,
        format_instructions: str = FORMAT_INSTRUCTIONS,
        input_variables: Optional[list[str]] = None,
        memory_prompts: Optional[list[BasePromptTemplate]] = None,
    ) -> BasePromptTemplate:
        tool_strings = []
        for tool in tools:
            args_schema = re.sub("}", "}}}}", re.sub("{", "{{{{", str(tool.args)))
            tool_strings.append(f"{tool.name}: {tool.description}, args: {args_schema}")
        formatted_tools = "\n".join(tool_strings)
        unique_tool_names = {tool.name for tool in tools}
        tool_names = ", ".join('"' + name + '"' for name in unique_tool_names)
        format_instructions = format_instructions.format(tool_names=tool_names)
        template = "\n\n".join([prefix, formatted_tools, format_instructions, suffix])
        if input_variables is None:
            input_variables = ["input", "agent_scratchpad"]
        _memory_prompts = memory_prompts or []
        messages = [
            SystemMessagePromptTemplate.from_template(template),
            *_memory_prompts,
            HumanMessagePromptTemplate.from_template(human_message_template),
        ]
        return ChatPromptTemplate(input_variables=input_variables, messages=messages)  # type: ignore[arg-type]

    def _construct_scratchpad(self, intermediate_steps: list[tuple[AgentAction, str]]) -> str:
        agent_scratchpad = ""
        for action, observation in intermediate_steps:
            agent_scratchpad += action.log
            agent_scratchpad += f"\n{self.observation_prefix}{observation}\n{self.llm_prefix}"

        if not isinstance(agent_scratchpad, str):
            raise ValueError("agent_scratchpad should be of type string.")
        if agent_scratchpad:
            return (
                f"This was your previous work "
                f"(but I haven't seen any of it! I only see what "
                f"you return as final answer):\n{agent_scratchpad}"
            )
        else:
            return agent_scratchpad

    @classmethod
    def from_llm_and_tools(
        cls,
        llm: BaseLanguageModel,
        tools: Sequence[BaseTool],
        callback_manager: Optional[BaseCallbackManager] = None,
        output_parser: Optional[AgentOutputParser] = None,
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        human_message_template: str = HUMAN_MESSAGE_TEMPLATE,
        format_instructions: str = FORMAT_INSTRUCTIONS,
        input_variables: Optional[list[str]] = None,
        memory_prompts: Optional[list[BasePromptTemplate]] = None,
        **kwargs: Any,
    ) -> Agent:
        """Construct an agent from an LLM and tools."""
        cls._validate_tools(tools)
        prompt = cls.create_prompt(
            tools,
            prefix=prefix,
            suffix=suffix,
            human_message_template=human_message_template,
            format_instructions=format_instructions,
            input_variables=input_variables,
            memory_prompts=memory_prompts,
        )

        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            callback_manager=callback_manager,
        )
        tool_names = [tool.name for tool in tools]
        _output_parser = output_parser
        return cls(
            llm_chain=llm_chain,
            allowed_tools=tool_names,
            output_parser=_output_parser,
            dataset_tools=tools,
            **kwargs,
        )
