from typing import Union, cast

from langchain_community.chat_models import ChatOllama as LCChatOllama
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)


class ChatOllama(LCChatOllama):
    def _convert_messages_to_ollama_messages(
        self, messages: list[BaseMessage]
    ) -> list[dict[str, Union[str, list[str]]]]:
        ollama_messages: list = []
        for message in messages:
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            elif isinstance(message, SystemMessage):
                role = "system"
            elif isinstance(message, ChatMessage):
                role = message.role
            else:
                raise ValueError("Received unsupported message type for Ollama.")

            content = ""
            images = []
            if isinstance(message.content, str):
                content = message.content
            else:
                for content_part in cast(list[dict], message.content):
                    if content_part.get("type") == "text":
                        content += f"\n{content_part['text']}"
                    elif content_part.get("type") == "image_url":
                        temp_image_url = content_part.get("image_url")
                        if isinstance(temp_image_url, str):
                            image_url = content_part["image_url"]
                        elif isinstance(temp_image_url, dict) and "url" in temp_image_url:
                            image_url = temp_image_url["url"]
                        else:
                            raise ValueError(
                                "Only string image_url or dict with string 'url' inside content parts are supported."
                            )

                        image_url_components = image_url.split(",")
                        # Support data:image/jpeg;base64,<image> format
                        # and base64 strings
                        if len(image_url_components) > 1:
                            images.append(image_url_components[1])
                        else:
                            images.append(image_url_components[0])

                    else:
                        raise ValueError(
                            "Unsupported message content type. "
                            "Must either have type 'text' or type 'image_url' "
                            "with a string 'image_url' field."
                        )

            ollama_messages.append(
                {
                    "role": role,
                    "content": content,
                    "images": images,
                }
            )

        return ollama_messages
