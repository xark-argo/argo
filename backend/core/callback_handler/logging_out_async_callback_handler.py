import logging
from typing import Any, Optional, Union
from uuid import UUID

from langchain.agents.output_parsers.tools import ToolAgentAction
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage, get_buffer_string
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk, LLMResult

from core.prompt.prompt_message_utils import truncate_image_base64

COLORS = {
    "blue": "\033[94m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "pink": "\033[38;5;198m",
    "endc": "\033[0m",
}


def logging_with_color(message: str, color: str = ""):
    color_code = COLORS.get(color, COLORS["endc"])
    formatted_message = f"{color_code}{message}{COLORS['endc']}"
    logging.info(formatted_message)


class LoggingOutAsyncCallbackHandler(AsyncCallbackHandler):
    """Callback Handler that prints to std out."""

    def __init__(self, color: Optional[str] = None) -> None:
        """Initialize callback handler."""
        self.color = color
        self.parent_run_id = ""

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        full_message = "[on_chat_model_start]"
        for sub_messages in messages:
            full_message += f"\n{get_buffer_string(sub_messages)}"
        logging_with_color(truncate_image_base64(full_message), color="blue")

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Print out the prompts."""
        logging_with_color(f"[on_llm_start]\n{prompts[0]}\n", color="blue")

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging_with_color(
            f"[on_llm_end]\nOutput: {str(response.generations[0][0].text)}",
            color="pink",
        )

    async def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        # logging_with_color(f"[on_llm_new_token]\nToken: " + token, color='green')
        pass

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging_with_color(f"[on_llm_error]\nError: {str(error)}", color="blue")

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging_with_color(f"[on_chain_error]\nError: {str(error)}", color="pink")

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        inputs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging_with_color(
            f"[on_tool_start]\ntool: {str(serialized)}\ninput: {input_str}",
            color="yellow",
        )

    async def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> Any:
        """Run on agent action."""
        tool = action.tool
        tool_input = action.tool_input
        if isinstance(action, ToolAgentAction):
            thought = action.log.strip()
        else:
            action_name_position = action.log.index("Action:") if action.log else -1
            thought = action.log[:action_name_position].strip() if action.log else ""
        log = f"Thought: {thought}\nTool: {tool}\nTool Input: {tool_input}"
        logging_with_color(f"[on_agent_action]\n{log}", color="green")

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """If not the final action, print out observation."""
        logging_with_color(f"[on_tool_end]\n{output}", color="yellow")

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging_with_color(f"[on_tool_error]\nError: {str(error)}", color="yellow")

    async def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run on agent end."""
        logging_with_color(f"[on_agent_finish]\n{finish.return_values['output']}", color="green")
