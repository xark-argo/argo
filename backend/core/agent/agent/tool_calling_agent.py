import uuid
from collections.abc import Sequence
from typing import Any, Callable, Union

from langchain.agents.agent import (
    RunnableMultiActionAgent as LCRunnableMultiActionAgent,
)
from langchain.agents.format_scratchpad.tools import format_to_tool_messages
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import Callbacks
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.tools import BaseTool

from core.agent.output_parser.tools import ToolsAgentOutputParser

MessageFormatter = Callable[[Sequence[tuple[AgentAction, str]]], list[BaseMessage]]


def format_stop_to_tool_messages(
    intermediate_steps: Sequence[tuple[AgentAction, str]],
) -> list[BaseMessage]:
    """Convert (AgentAction, tool output) tuples into ToolMessages.

    Args:
        intermediate_steps: Steps the LLM has taken to date, along with observations.

    Returns:
        list of messages to send to the LLM for the next prediction.

    """
    messages = format_to_tool_messages(intermediate_steps)
    messages.append(HumanMessage(content="I now need to return a final answer based on the previous steps."))

    return messages


class RunnableMultiActionAgent(LCRunnableMultiActionAgent):
    """Agent powered by Runnables."""

    runnable_not_tool: Runnable[dict, Union[list[AgentAction], AgentFinish]]
    callbacks: Callbacks

    async def aplan(
        self,
        intermediate_steps: list[tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[
        list[AgentAction],
        AgentFinish,
    ]:
        """Async based on past history and current inputs, decide what to do.

        Args:
            intermediate_steps: Steps the LLM has taken to date,
                along with observations.
            callbacks: Callbacks to run.
            **kwargs: User inputs.

        Returns:
            Action specifying what tool to use.
        """
        new_intermediate_steps = []

        for intermediate_step in intermediate_steps:
            action, observation = intermediate_step
            if isinstance(observation, ToolMessage):
                observation = observation.content

            new_intermediate_steps.append((action, observation))

        inputs = {**kwargs, **{"intermediate_steps": new_intermediate_steps}}
        final_output: Any = None
        if self.stream_runnable:
            # Use streaming to make sure that the underlying LLM is invoked in a
            # streaming
            # fashion to make it possible to get access to the individual LLM tokens
            # when using stream_log with the Agent Executor.
            # Because the response from the plan is not a generator, we need to
            # accumulate the output into final output and return that.
            async for chunk in self.runnable.astream(inputs, config={"callbacks": callbacks}):
                if final_output is None:
                    final_output = chunk
                else:
                    final_output += chunk
        else:
            final_output = await self.runnable.ainvoke(inputs, config={"callbacks": callbacks})

        return final_output  # type: ignore

    def return_stopped_response(
        self,
        early_stopping_method: str,
        intermediate_steps: list[tuple[AgentAction, str]],
        **kwargs: Any,
    ) -> AgentFinish:
        """Return response when agent has been stopped due to max iterations.

        Args:
            early_stopping_method: Method to use for early stopping.
            intermediate_steps: Steps the LLM has taken to date,
                along with observations.
            **kwargs: User inputs.

        Returns:
            AgentFinish: Agent finish object.

        Raises:
            ValueError: If `early_stopping_method` is not in ['force', 'generate'].
        """
        if early_stopping_method == "force":
            # `force` just returns a constant string
            return AgentFinish({"output": "Agent stopped due to iteration limit or time limit."}, "")
        elif early_stopping_method == "generate":
            new_intermediate_steps = []

            for intermediate_step in intermediate_steps:
                action, observation = intermediate_step
                if isinstance(observation, ToolMessage):
                    observation = observation.content

                new_intermediate_steps.append((action, observation))

            inputs = {**kwargs, **{"intermediate_steps": new_intermediate_steps}}
            agent_decision = self.runnable_not_tool.invoke(inputs, config={"callbacks": self.callbacks})
            if isinstance(agent_decision, AgentFinish):
                return agent_decision
            else:
                raise ValueError(f"got AgentAction with no functions provided: {agent_decision}")
        else:
            raise ValueError(
                f"early_stopping_method should be one of `force` or `generate`, got {early_stopping_method}"
            )

    def tool_run_logging_kwargs(self) -> dict:
        """Return logging kwargs for tool run."""
        return {
            "tool_call_id": uuid.uuid4().hex,
        }


def create_tool_calling_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: ChatPromptTemplate,
    callbacks: Callbacks,
    *,
    message_formatter: MessageFormatter = format_to_tool_messages,
) -> RunnableMultiActionAgent:
    """Create an agent that uses tools.

    Args:
        llm: LLM to use as the agent.
        tools: Tools this agent has access to.
        prompt: The prompt to use. See Prompt section below for more on the expected
            input variables.
        callbacks: Callbacks.
        message_formatter: Formatter function to convert (AgentAction, tool output)
            tuples into FunctionMessages.

    Returns:
        A Runnable sequence representing an agent. It takes as input all the same input
        variables as the prompt passed in does. It returns as output either an
        AgentAction or AgentFinish.

    Example:

        .. code-block:: python

            from langchain.agents import AgentExecutor, create_tool_calling_agent, tool
            from langchain_anthropic import ChatAnthropic
            from langchain_core.prompts import ChatPromptTemplate

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "You are a helpful assistant"),
                    ("placeholder", "{chat_history}"),
                    ("human", "{input}"),
                    ("placeholder", "{agent_scratchpad}"),
                ]
            )
            model = ChatAnthropic(model="claude-3-opus-20240229")

            @tool
            def magic_function(input: int) -> int:
                \"\"\"Applies a magic function to an input.\"\"\"
                return input + 2

            tools = [magic_function]

            agent = create_tool_calling_agent(model, tools, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

            agent_executor.invoke({"input": "what is the value of magic_function(3)?"})

            # Using with chat history
            from langchain_core.messages import AIMessage, HumanMessage
            agent_executor.invoke(
                {
                    "input": "what's my name?",
                    "chat_history": [
                        HumanMessage(content="hi! my name is bob"),
                        AIMessage(content="Hello Bob! How can I assist you today?"),
                    ],
                }
            )

    Prompt:

        The agent prompt must have an `agent_scratchpad` key that is a
            ``MessagesPlaceholder``. Intermediate agent actions and tool output
            messages will be passed in here.
    """
    missing_vars = {"agent_scratchpad"}.difference(prompt.input_variables + list(prompt.partial_variables))
    if missing_vars:
        raise ValueError(f"Prompt missing required variables: {missing_vars}")

    if not hasattr(llm, "bind_tools"):
        raise ValueError(
            "This function requires a .bind_tools method be implemented on the LLM.",
        )

    def build_agent_chain(llm_component: Runnable, formatter: MessageFormatter) -> Runnable:
        return (
            RunnablePassthrough.assign(agent_scratchpad=lambda x: formatter(x["intermediate_steps"]))
            | prompt
            | llm_component
            | ToolsAgentOutputParser()
        )

    llm_with_tools = llm.bind_tools(tools) if bool(tools) else llm
    tool_aware_chain = build_agent_chain(llm_with_tools, message_formatter)
    plain_llm_chain = build_agent_chain(llm, format_stop_to_tool_messages)

    return RunnableMultiActionAgent(
        runnable=tool_aware_chain,
        stream_runnable=True,
        runnable_not_tool=plain_llm_chain,
        callbacks=callbacks,
    )
