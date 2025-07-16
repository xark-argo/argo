import json
import logging
from copy import deepcopy
from datetime import datetime
from typing import Optional

from core.callback_handler.logging_out_callback_handler import (
    LoggingOutCallbackHandler,
)
from core.entities.application_entities import InvokeFrom
from core.errors.notfound import NotFoundError
from core.errors.validate import ValidateError
from core.model_providers import model_provider_manager
from database.db import session_scope
from models.bot import Bot, get_model_config
from models.conversation import (
    Conversation,
    DatasetRetrieverResource,
    Message,
    MessageAgentThought,
    get_conversation,
    get_message,
)
from services.bot.bot_service import BotService
from services.chat.util import get_file_docs

CONVERSATION_TITLE_PROMPT = """You need to decompose the user's input into "subject" and "intention" in order to \
accurately figure out what the user's input language actually is. 
Notice: the language type user use could be diverse, \
which can be English, Chinese, Español, Arabic, Japanese, French, and etc.
MAKE SURE your output is the SAME language as the user's input!
Your output is restricted only to: (Input language) Intention + Subject(short as possible)
Your output MUST be a valid JSON.

Tip: When the user's question is directed at you (the language model), you can add an emoji to make it more fun.


example 1:
User Input: hi, yesterday i had some burgers.
{
  "Language Type": "The user's input is pure English",
  "Your Reasoning": "The language of my output must be pure English.",
  "Your Output": "sharing yesterday's food"
}

example 2:
User Input: hello
{
  "Language Type": "The user's input is written in pure English",
  "Your Reasoning": "The language of my output must be pure English.",
  "Your Output": "Greeting myself☺️"
}


example 3:
User Input: why mmap file: oom
{
  "Language Type": "The user's input is written in pure English",
  "Your Reasoning": "The language of my output must be pure English.",
  "Your Output": "Asking about the reason for mmap file: oom"
}


example 4:
User Input: www.convinceme.yesterday-you-ate-seafood.tv讲了什么？
{
  "Language Type": "The user's input English-Chinese mixed",
  "Your Reasoning": "The English-part is an URL, the main intention is still written in Chinese, so the language \
  of my output must be using Chinese.",
  "Your Output": "询问网站www.convinceme.yesterday-you-ate-seafood.tv"
}

example 5:
User Input: why小红的年龄is老than小明？
{
  "Language Type": "The user's input is English-Chinese mixed",
  "Your Reasoning": "The English parts are subjective particles, the main intention is written in Chinese, \
  besides, Chinese occupies a greater \"actual meaning\" than English, \
  so the language of my output must be using Chinese.",
  "Your Output": "询问小红和小明的年龄"
}

example 6:
User Input: yo, 你今天咋样？
{
  "Language Type": "The user's input is English-Chinese mixed",
  "Your Reasoning": "The English-part is a subjective particle, the main intention is written in Chinese, \
  so the language of my output must be using Chinese.",
  "Your Output": "查询今日我的状态☺️"
}

User Input: 
"""


class ConversationService:
    @classmethod
    def pagination_by_last_id(cls, user_id: str, last_id: Optional[str], limit: int) -> tuple[list[Conversation], bool]:
        with session_scope() as session:
            base_query = (
                session.query(Conversation)
                .join(Bot, Conversation.bot_id == Bot.id)
                .filter(
                    Conversation.is_deleted == False,
                    Conversation.invoke_from == InvokeFrom.WEB_APP.value,
                    Conversation.from_user_id == user_id,
                )
            )

            if last_id:
                last_conversation = base_query.filter(
                    Conversation.id == last_id,
                ).first()

                if not last_conversation:
                    raise NotFoundError("Last conversation with id {} not found".format(last_id))

                conversations = (
                    base_query.filter(
                        Conversation.updated_at < last_conversation.updated_at,
                        Conversation.id != last_conversation.id,
                    )
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                    .all()
                )
            else:
                conversations = base_query.order_by(Conversation.updated_at.desc()).limit(limit).all()

            has_more = False
            if len(conversations) == limit:
                current_page_first_conversation = conversations[-1]
                rest_count = base_query.filter(
                    Conversation.updated_at < current_page_first_conversation.updated_at,
                    Conversation.id != current_page_first_conversation.id,
                ).count()

                if rest_count > 0:
                    has_more = True

        bot_ids = list({conversation.bot_id for conversation in conversations})
        bots_info = BotService.get_bots_info(bot_ids)
        for conversation in conversations:
            conversation.bot_name = getattr(bots_info.get(conversation.bot_id), "name", "")
            conversation.bot_icon = getattr(bots_info.get(conversation.bot_id), "icon", "")
            conversation.latest_answer = MessageService.get_latest_answer(conversation.id)

        return conversations, has_more

    @classmethod
    def create(cls, user_id: str) -> Conversation:
        with session_scope() as session:
            conversation = Conversation(
                mode="chat",
                name="New conversation",
                inputs={},
                system_instruction="",
                system_instruction_tokens=0,
                status="normal",
                from_source="api",
                from_user_id=user_id,
                invoke_from=InvokeFrom.WEB_APP.value,
            )
            session.add(conversation)
            session.commit()
            session.refresh(conversation)

        return conversation

    @classmethod
    def delete(cls, conversation_id: str):
        if not conversation_id:
            raise ValidateError("Missing required field: conversation_id")

        with session_scope() as session:
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation:
                conversation.is_deleted = True
                session.commit()

    @classmethod
    def clear_messages(cls, conversation_id: str):
        if not conversation_id:
            raise ValidateError("Missing required field: conversation_id")

        with session_scope() as session:
            session.query(Message).filter_by(conversation_id=conversation_id).delete()

            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation and conversation.chat_metadata:
                if "timed_world_info" in conversation.chat_metadata:
                    chat_metadata = deepcopy(conversation.chat_metadata)
                    del chat_metadata["timed_world_info"]
                    conversation.chat_metadata = chat_metadata
                    session.commit()

    @classmethod
    def rename(cls, conversation_id: str, name: str, auto_generate: bool) -> Conversation:
        if not conversation_id:
            raise ValidateError("Missing required field: conversation_id")

        with session_scope() as session:
            conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise NotFoundError("Conversation with id {} not found".format(conversation_id))

        if auto_generate:
            name = cls.auto_generate_name(conversation)

        if not name:
            return conversation

        with session_scope() as session:
            session.query(Conversation).filter_by(id=conversation.id).update({Conversation.name: name})
            session.commit()
        conversation.name = name

        return conversation

    @classmethod
    def auto_generate_name(cls, conversation: Conversation) -> str:
        if not conversation:
            return ""

        # get conversation first message
        with session_scope() as session:
            message = (
                session.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.asc())
                .first()
            )

            if not message:
                raise NotFoundError("Conversation message not exists")

        # generate conversation name
        try:
            name = cls.generate_conversation_name(conversation.bot_model_config_id, message.query)
            return name
        except Exception as e:
            logging.exception("Generate conversation name")
            pass
            return ""

    @classmethod
    def generate_conversation_name(cls, bot_model_config_id: str, query: str) -> str:
        prompt = CONVERSATION_TITLE_PROMPT

        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]

        query = query.replace("\n", " ")
        prompt += query + "\n"

        bot_model_config = get_model_config(bot_model_config_id)
        if not bot_model_config:
            raise ValueError("Bot model config broken")

        model_dict = bot_model_config.model_dict
        model_name = model_dict.get("name")
        if not model_name:
            return ""

        provider = model_dict.get("provider")

        params = {
            "num_predict": 100,
            "temperature": 1,
        }

        llm_instance = model_provider_manager.get_model_instance(provider, model_name, params)
        llm_instance.callbacks = [LoggingOutCallbackHandler()]
        response = llm_instance.invoke(prompt)

        result_dict = json.loads(response.content)
        name = result_dict.get("Your Output", "").strip()

        return name[:75] + "..." if len(name) > 75 else str(name)

    @classmethod
    def create_branch(cls, conversation_id: str, message_id: str) -> Conversation:
        with session_scope() as session:
            # 1. 原始对话 & 分支点消息
            original_conversation = session.query(Conversation).filter_by(id=conversation_id, is_deleted=False).first()
            if not original_conversation:
                raise NotFoundError(f"Conversation with id {conversation_id} not found")

            message = session.query(Message).filter_by(id=message_id).first()
            if not message:
                raise NotFoundError(f"Message with id {message_id} not found")

            messages_to_copy = (
                session.query(Message)
                .filter(
                    Message.conversation_id == conversation_id,
                    (Message.created_at < message.created_at) | (Message.id == message_id),
                )
                .order_by(Message.created_at)
                .all()
            )

            if not messages_to_copy:
                raise ValueError(f"No messages found for conversation {conversation_id} from message {message_id}")

            file_docs = [doc for msg in messages_to_copy for doc in get_file_docs(msg.files)]

            # 2. 创建新 Conversation
            new_conversation = Conversation(
                bot_id=original_conversation.bot_id,
                bot_model_config_id=original_conversation.bot_model_config_id,
                model_provider=original_conversation.model_provider,
                model_id=original_conversation.model_id,
                mode=original_conversation.mode,
                name=original_conversation.name,
                inputs=original_conversation.inputs,
                docs=file_docs,
                datasets=original_conversation.datasets,
                system_instruction=original_conversation.system_instruction,
                system_instruction_tokens=original_conversation.system_instruction_tokens,
                status=original_conversation.status,
                from_source=original_conversation.from_source,
                from_user_id=original_conversation.from_user_id,
                invoke_from=original_conversation.invoke_from,
                created_at=original_conversation.created_at,
                updated_at=datetime.now(),
            )
            session.add(new_conversation)
            session.commit()
            session.refresh(new_conversation)

            # 3. 拷贝 Message
            new_messages = []
            for msg in messages_to_copy:
                new_msg = Message(
                    bot_id=msg.bot_id,
                    model_provider=msg.model_provider,
                    model_id=msg.model_id,
                    conversation_id=new_conversation.id,
                    inputs=msg.inputs,
                    query=msg.query,
                    files=msg.files,
                    message=msg.message,
                    message_tokens=msg.message_tokens,
                    answer=msg.answer,
                    answer_tokens=msg.answer_tokens,
                    status=msg.status,
                    error=msg.error,
                    message_metadata=msg.message_metadata,
                    provider_response_latency=msg.provider_response_latency,
                    invoke_from=msg.invoke_from,
                    from_source=msg.from_source,
                    from_user_id=msg.from_user_id,
                    agent_based=msg.agent_based,
                    is_stopped=msg.is_stopped,
                    created_at=msg.created_at,
                    updated_at=msg.updated_at,
                )
                new_messages.append(new_msg)

            session.bulk_save_objects(new_messages, return_defaults=True)
            session.flush()

            # 4. 拷贝 MessageAgentThought
            old_to_new_msg_map = {old.id: new for old, new in zip(messages_to_copy, new_messages)}

            thoughts_to_copy = (
                session.query(MessageAgentThought)
                .filter(MessageAgentThought.message_id.in_(old_to_new_msg_map.keys()))
                .order_by(MessageAgentThought.position)
                .all()
            )

            new_thoughts = []
            for thought in thoughts_to_copy:
                new_msg = old_to_new_msg_map[thought.message_id]

                new_thoughts.append(
                    MessageAgentThought(
                        message_id=new_msg.id,
                        position=thought.position,
                        thought=thought.thought,
                        tool=thought.tool,
                        tool_input=thought.tool_input,
                        tool_type=thought.tool_type,
                        tool_meta=thought.tool_meta,
                        meta=thought.meta,
                        observation=thought.observation,
                        tool_process_data=thought.tool_process_data,
                        tool_time_cost=thought.tool_time_cost,
                        message=thought.message,
                        message_token=thought.message_token,
                        answer=thought.answer,
                        answer_token=thought.answer_token,
                        status=thought.status,
                        tokens=thought.tokens,
                        currency=thought.currency,
                        latency=thought.latency,
                        created_by_role=thought.created_by_role,
                        created_by=thought.created_by,
                        created_at=thought.created_at,
                    )
                )
            session.bulk_save_objects(new_thoughts, return_defaults=True)
            session.flush()

            # 5. 拷贝 DatasetRetrieverResource
            old_to_new_thought_map = {old.id: new for old, new in zip(thoughts_to_copy, new_thoughts)}

            retriever_resources = (
                session.query(DatasetRetrieverResource)
                .filter(DatasetRetrieverResource.message_id.in_(old_to_new_msg_map.keys()))
                .all()
            )

            new_resources = []
            for res in retriever_resources:
                new_msg = old_to_new_msg_map[res.message_id]
                new_thought_id = None
                if res.message_agent_thought_id:
                    new_thought = old_to_new_thought_map.get(res.message_agent_thought_id)
                    new_thought_id = new_thought.id if new_thought else None

                new_resources.append(
                    DatasetRetrieverResource(
                        message_id=new_msg.id,
                        position=res.position,
                        message_agent_thought_id=new_thought_id,
                        dataset_id=res.dataset_id,
                        dataset_name=res.dataset_name,
                        document_path=res.document_path,
                        document_name=res.document_name,
                        score=res.score,
                        start_index=res.start_index,
                        content=res.content,
                        created_by=res.created_by,
                        created_at=res.created_at,
                    )
                )
            session.bulk_save_objects(new_resources)

            session.commit()
            return new_conversation


class MessageService:
    @classmethod
    def pagination_by_first_id(
        cls, conversation_id: Optional[str], first_id: Optional[str], limit: int
    ) -> tuple[list[Message], bool]:
        if not conversation_id:
            raise ValidateError("Missing required field: conversation_id")

        conversation = get_conversation(conversation_id)

        if not conversation:
            raise NotFoundError(f"Conversation with id {conversation_id} not found")

        with session_scope() as session:
            if first_id:
                first_message = (
                    session.query(Message)
                    .filter(
                        Message.conversation_id == conversation.id,
                        Message.id == first_id,
                    )
                    .first()
                )

                if not first_message:
                    raise NotFoundError("First message with id {} not found".format(first_id))

                history_messages = (
                    session.query(Message)
                    .filter(
                        Message.conversation_id == conversation.id,
                        Message.created_at < first_message.created_at,
                        Message.id != first_message.id,
                    )
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                    .all()
                )
            else:
                history_messages = (
                    session.query(Message)
                    .filter(Message.conversation_id == conversation.id)
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                    .all()
                )

            has_more = False
            if len(history_messages) == limit:
                current_page_first_message = history_messages[-1]
                rest_count = (
                    session.query(Message)
                    .filter(
                        Message.conversation_id == conversation.id,
                        Message.created_at < current_page_first_message.created_at,
                        Message.id != current_page_first_message.id,
                    )
                    .count()
                )

                if rest_count > 0:
                    has_more = True

        history_messages = list(reversed(history_messages))

        return history_messages, has_more

    @classmethod
    def get_latest_answer(cls, conversation_id: str) -> str:
        with session_scope() as session:
            latest_message = (
                session.query(Message)
                .filter(Message.conversation_id == conversation_id, Message.answer != "")
                .order_by(Message.created_at.desc())
                .first()
            )

            if latest_message:
                return latest_message.answer

        return ""

    @classmethod
    def update(
        cls,
        message_id: str,
        query: str,
        answer: str,
        final_thought_id: Optional[str] = None,
    ):
        with session_scope() as session:
            message = session.query(Message).filter_by(id=message_id).first()

            if not message:
                raise NotFoundError(f"Message with id {message_id} not found")

            message.query = query
            message.answer = answer

            if final_thought_id:
                session.query(MessageAgentThought).filter_by(id=final_thought_id, message_id=message.id).update(
                    {MessageAgentThought.thought: answer}
                )

            session.commit()

            return message

    @classmethod
    def delete(cls, message_id: str, delete_query: bool = False, delete_answer: bool = False):
        message = get_message(message_id)
        if not message:
            raise ValueError(f"Message with id {message_id} not found")

        if delete_query and message.files:
            doc_ids = get_file_docs(message.files)
            if doc_ids:
                with session_scope() as session:
                    conversation = session.query(Conversation).filter_by(id=message.conversation_id).first()
                    if conversation:
                        conversation.docs = [doc_id for doc_id in conversation.docs if doc_id not in doc_ids]
                        session.commit()

        with session_scope() as session:
            message = session.query(Message).filter_by(id=message_id).first()
            if not message:
                raise ValueError(f"Message with id {message_id} not found")

            if delete_query:
                message.query = None
                message.query_deleted = True
                message.files = []

            if delete_answer:
                # 删除关联的 MessageAgentThought
                session.query(MessageAgentThought).filter(MessageAgentThought.message_id == message.id).delete(
                    synchronize_session=False
                )

                message.answer = None
                message.answer_deleted = True

            if message.query is None and message.answer is None:
                session.delete(message)
                session.commit()
                return None

            session.commit()
            return message
