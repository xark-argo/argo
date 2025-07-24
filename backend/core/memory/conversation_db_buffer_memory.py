import re
from typing import Any, Optional, Union

from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    get_buffer_string,
)

from core.file.message_file_parser import MessageFileParser
from models.conversation import filter_message


def trim_answer(content: str) -> str:
    # trim <think>, <display>
    return re.sub(r"<(think|display)>.*?</\1>", "", content, flags=re.DOTALL)


class ConversationBufferDBMemory(BaseChatMemory):
    bot_id: str = ""
    conversation_id: str = ""
    regen_message_id: Optional[str] = None
    human_prefix: str = "Human"
    ai_prefix: str = "Assistant"
    llm: Optional[BaseLanguageModel] = None
    memory_key: str = "chat_history"
    max_token_limit: int = 20000
    message_limit: int = 500

    @property
    def buffer(self) -> list[BaseMessage]:
        """String buffer of memory."""
        # fetch limited messages desc, and return reversed
        chat_messages: list[BaseMessage] = []
        if not self.conversation_id or not self.llm:
            return chat_messages

        messages = filter_message(
            conversation_id=self.conversation_id,
            before_message_id=self.regen_message_id,
            message_limit=self.message_limit,
        )

        messages = list(reversed(messages))
        message_file_parser = MessageFileParser(bot_id=self.bot_id)

        for message in messages:
            if message.query or message.files:
                if message.files:
                    file_objs = message_file_parser.transform_message_files(message.files)
                    if not file_objs:
                        chat_messages.append(HumanMessage(name=self.human_prefix, content=message.query))
                    else:
                        prompt_message_contents: list[Union[str, dict]] = [{"type": "text", "text": message.query}]
                        for file_obj in file_objs:
                            prompt_message_contents.append(file_obj.prompt_message_content)

                        chat_messages.append(HumanMessage(name=self.human_prefix, content=prompt_message_contents))
                elif message.query:
                    chat_messages.append(HumanMessage(name=self.human_prefix, content=message.query))
            if message.answer:
                chat_messages.append(AIMessage(name=self.ai_prefix, content=trim_answer(message.answer)))

        if not chat_messages:
            return []

        # prune the chat message if it exceeds the max token limit
        # curr_buffer_length = self.llm.get_num_tokens_from_messages(chat_messages)
        # if curr_buffer_length > self.max_token_limit:
        #     pruned_memory = []
        #     while curr_buffer_length > self.max_token_limit and chat_messages:
        #         pruned_memory.append(chat_messages.pop(0))
        #         curr_buffer_length = self.llm.get_num_tokens_from_messages(chat_messages)

        return chat_messages

    @property
    def memory_variables(self) -> list[str]:
        """Will always return list of memory variables.

        :meta private:
        """
        return [self.memory_key]

    def load_memory_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Return history buffer."""
        buffer: Any = self.buffer
        if self.return_messages:
            final_buffer: Any = buffer
        else:
            final_buffer = get_buffer_string(
                buffer,
                human_prefix=self.human_prefix,
                ai_prefix=self.ai_prefix,
            )
        return {self.memory_key: final_buffer}

    def save_context(self, inputs: dict[str, Any], outputs: dict[str, str]) -> None:
        """Nothing should be saved or changed"""
        pass

    def clear(self) -> None:
        """Nothing to clear, got a memory like a vault."""
        pass
