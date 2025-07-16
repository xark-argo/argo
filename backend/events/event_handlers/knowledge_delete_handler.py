import json
import logging

from database.db import session_scope
from events.knowledge_event import knowledge_delete
from models.bot import BotModelConfig
from models.conversation import Conversation


@knowledge_delete.connect
def handle(sender, **kwargs):
    knowledge_id = sender
    knowledge_name = kwargs.get("knowledge_name")

    if knowledge_id is None:
        return

    # --- 更新 BotModelConfig ---
    with session_scope() as session:
        model_configs = session.query(BotModelConfig).all()
        for model_config in model_configs:
            try:
                agent = model_config.agent_mode_dict or {}
                tools = agent.get("tools", [])
                original_len = len(tools)

                tools[:] = [tool for tool in tools if tool.get("id") != knowledge_id]

                if len(tools) < original_len:
                    affected = (
                        session.query(BotModelConfig)
                        .filter(
                            BotModelConfig.id == model_config.id,
                            BotModelConfig.updated_at == model_config.updated_at,
                        )
                        .update(
                            {
                                "agent_mode": json.dumps(agent),
                                "updated_at": model_config.updated_at,
                            },
                            synchronize_session=False,
                        )
                    )

                    if affected:
                        logging.info(f"Updated BotModelConfig {model_config.id} tool '{knowledge_name}'")
                    else:
                        logging.warning(f"Skipped BotModelConfig {model_config.id} — modified by others.")
            except Exception as e:
                logging.exception(f"Failed to update BotModelConfig {model_config.id}")
                pass

        # --- 更新 Conversation.tools ---
        conversations = session.query(Conversation).all()
        for conversation in conversations:
            try:
                tools = conversation.tools or []
                original_len = len(tools)

                tools[:] = [tool for tool in tools if tool.get("id") != knowledge_id]
                found = len(tools) < original_len

                datasets = conversation.datasets or {}
                if knowledge_id in datasets:
                    del datasets[knowledge_id]
                    found = True

                if found:
                    affected = (
                        session.query(Conversation)
                        .filter(
                            Conversation.id == conversation.id,
                            Conversation.updated_at == conversation.updated_at,
                        )
                        .update(
                            {"datasets": datasets, "tools": tools, "updated_at": conversation.updated_at},
                            synchronize_session=False,
                        )
                    )

                    if affected:
                        logging.info(f"Updated Conversation {conversation.id} tool '{knowledge_name}'")
                    else:
                        logging.warning(f"Skipped Conversation {conversation.id} — modified by others.")
            except Exception as e:
                logging.exception(f"Failed to update Conversation {conversation.id}")
                pass
