import logging
import re
from typing import Any, Optional, Union
from uuid import UUID

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import BaseCallbackHandler
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


class LoggingOutCallbackHandler(BaseCallbackHandler):
    """Callback Handler that prints to std out."""

    def __init__(self, color: Optional[str] = None) -> None:
        """Initialize callback handler."""
        self.color = color
        self.parent_run_id = ""

    def on_chat_model_start(
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

    def on_llm_start(
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

    def on_llm_end(
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

    def on_llm_new_token(
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

    def on_llm_error(
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

    # def on_chain_start(
    #         self,
    #         serialized: dict[str, Any],
    #         inputs: dict[str, Any],
    #         *,
    #         run_id: UUID,
    #         parent_run_id: Optional[UUID] = None,
    #         tags: Optional[list[str]] = None,
    #         metadata: Optional[dict[str, Any]] = None,
    #         **kwargs: Any,
    # ) -> None:
    #     """Print out that we are entering a chain."""
    #     chain_type = serialized['id'][-1]
    #     logging_with_color(f"[on_chain_start]\nChain: {chain_type}\nInputs: {str(inputs)}", color='pink')

    # def on_chain_end(
    #         self,
    #         outputs: dict[str, Any],
    #         *,
    #         run_id: UUID,
    #         parent_run_id: Optional[UUID] = None,
    #         **kwargs: Any,
    # ) -> None:
    #     """Print out that we finished a chain."""
    #     logging_with_color(f"[on_chain_end]\nOutputs: {str(outputs)}", color='pink')

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        logging_with_color(f"[on_chain_error]\nError: {str(error)}", color="pink")

    def on_tool_start(
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
        logging_with_color(f"[on_tool_start]\n{str(serialized)}", color="yellow")

    def on_agent_action(
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
        try:
            action_log = action.log or ""
            match = re.search(r"(\nAction:|<\|action_start\|>)", action_log)
            action_name_position = match.start() if match else -1
            thought = action.log[:action_name_position].strip() if action.log else ""
        except ValueError:
            thought = ""

        log = f"Thought: {thought}\nTool: {tool}\nTool Input: {tool_input}"
        logging_with_color(f"[on_agent_action]\n{log}", color="green")

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """If not the final action, print out observation."""
        logging_with_color(f"[on_tool_end]\n{output}", color="yellow")

    def on_tool_error(
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

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run on agent end."""
        logging_with_color(f"[on_agent_finish]\n{finish.return_values['output']}", color="green")
