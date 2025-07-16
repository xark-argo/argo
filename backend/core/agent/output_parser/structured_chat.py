import json
import re
from typing import Union

from langchain.agents.structured_chat.output_parser import (
    StructuredChatOutputParser as LCStructuredChatOutputParser,
)
from langchain.agents.structured_chat.output_parser import (
    logger,
)
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException


class StructuredChatOutputParser(LCStructuredChatOutputParser):
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            pattern = re.compile(r"(?:```(?:json\s+)?\s*({.*})```|(?:json\s+)?\s*({.*}))", re.DOTALL)
            action_match = pattern.search(text)
            if action_match is not None:
                action_json = action_match.group(1) or action_match.group(2)
                response = json.loads(action_json.strip(), strict=False)
                if isinstance(response, list):
                    # gpt turbo frequently ignores the directive to emit a single action
                    logger.warning("Got multiple action responses: %s", response)
                    response = response[0]
                if "action" not in response or "action_input" not in response:
                    return AgentFinish({"output": text}, text)
                elif response["action"] == "Final Answer":
                    return AgentFinish({"output": response["action_input"]}, text)
                else:
                    return AgentAction(response["action"], response.get("action_input", {}), text)
            else:
                return AgentFinish({"output": text}, text)
        except Exception as e:
            raise OutputParserException(f"Could not parse LLM output: {text}, {e}")
