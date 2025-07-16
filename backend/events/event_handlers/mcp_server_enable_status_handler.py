import json
import logging

from database.db import session_scope
from events.mcp_server_event import mcp_server_enable_status
from models.bot import BotModelConfig
from models.conversation import Conversation


@mcp_server_enable_status.connect
def handle(sender, **kwargs):
    server_id = sender
    enable = kwargs.get("enable")
    server_name = kwargs.get("server_name")

    if server_id is None or enable is None:
        return

    # --- 更新 BotModelConfig ---
    with session_scope() as session:
        model_configs = session.query(BotModelConfig).all()
        for model_config in model_configs:
            try:
                agent = model_config.agent_mode_dict or {}
                tools = agent.get("tools", [])
                updated = False

                for tool in tools:
                    if tool.get("id") == server_id and tool["enabled"] != enable:
                        tool["enabled"] = enable
                        updated = True
                        break

                if updated:
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
                        logging.info(
                            f"Updated BotModelConfig {model_config.id} tool '{server_name}' enabled = {enable}"
                        )
                    else:
                        logging.warning(f"Skipped BotModelConfig {model_config.id} — modified by others.")
            except Exception as e:
                logging.exception(f"Failed to update BotModelConfig {model_config.id}")
                pass

        # --- 更新 Conversation.tools ---
        conversations = session.query(Conversation).all()
        for conversation in conversations:
            try:
                if conversation.is_deleted:
                    continue

                tools = conversation.tools or []
                updated = False

                for tool in tools:
                    if tool.get("id") == server_id and tool["enabled"] != enable:
                        tool["enabled"] = enable
                        updated = True

                if updated:
                    affected = (
                        session.query(Conversation)
                        .filter(
                            Conversation.id == conversation.id,
                            Conversation.updated_at == conversation.updated_at,
                        )
                        .update(
                            {"tools": tools, "updated_at": conversation.updated_at},
                            synchronize_session=False,
                        )
                    )

                    if affected:
                        logging.info(f"Updated Conversation {conversation.id} tool '{server_name}' enabled = {enable}")
                    else:
                        logging.warning(f"Skipped Conversation {conversation.id} — modified by others.")
            except Exception as e:
                logging.exception(f"Failed to update Conversation {conversation.id}")
                pass
