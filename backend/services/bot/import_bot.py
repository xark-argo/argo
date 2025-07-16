import json
import logging
import os.path
import uuid
from typing import cast

import requests
import yaml

from configs.env import MILVUS_DISTANCE_METHOD
from configs.settings import FILE_SETTINGS
from core.errors.validate import ValidateError
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_model_exist
from database import db
from models.bot import Bot, BotCategory, BotModelConfig, BotStatus
from models.document import DOCUMENTSTATUS, Document
from models.model_manager import DownloadStatus
from models.user import get_user
from services.bot.model_template import char_template
from services.bot.utils import import_user_input, init_prompt, reverse_transform_input
from services.common.provider_setting_service import get_provider_setting
from services.doc.doc_db import CollectionDB, DocDB
from services.file.file_op import upload_file
from services.model.model_service import ModelService

default_icon_url = "https://s2.loli.net/2024/09/27/NtCqJShAnMPZYw3.png"


class ImportBotService:
    @staticmethod
    def import_bot_from_yaml(space_id: str, user_id: str, bot_file: str) -> Bot:
        import_data = ImportBotService.load_yml_file(bot_file)

        tool_id_map = ImportBotService.process_tools(space_id, user_id, import_data)

        bot = ImportBotService.process_bot(space_id, user_id, import_data, tool_id_map)

        ImportBotService.process_models(bot, user_id, import_data)

        ImportBotService.process_knowledge(bot, space_id, user_id, import_data)

        return bot

    @staticmethod
    def process_bot(space_id: str, user_id: str, import_data: dict, tool_id_map: dict) -> Bot:
        """
        Create and persist a Bot instance based on imported data.
        """
        bot_data = import_data.get("bot", {})
        icon = ImportBotService.import_asset_from_url(user_id, bot_data.get("icon"), "icon.png", default_icon_url)
        background_img = ImportBotService.import_asset_from_url(
            user_id, bot_data.get("background_img"), "background.png"
        )
        category = bot_data.get("category", BotCategory.ASSISTANT.value)
        if not category:
            category = BotCategory.ASSISTANT.value
        bot = Bot(
            space_id=space_id,
            mode=bot_data.get("mode"),
            name=bot_data.get("name"),
            description=bot_data.get("description", ""),
            category=category,
            icon=icon,
            background_img=background_img,
            status=BotStatus.BOT_UNINSTALL.value,
        )
        user = get_user(user_id)
        user_name = user.username

        model_config_data = import_data.get("model_config")
        with db.session_scope() as session:
            session.add(bot)
            session.commit()
            if model_config_data:
                user_input_form = model_config_data.get("user_input_form", [])
                model_config_data.update({"user_input_form": reverse_transform_input(user_input_form)})
                bot_model_config = BotModelConfig()
                bot_model_config = bot_model_config.from_model_config_dict(model_config_data)
                bot_model_config.tool_config = []
                if category == BotCategory.ROLEPLAY.value:
                    bot_model_config.silly_character = char_template
                    bot_model_config.pre_prompt = init_prompt()
                    if not bot_model_config.user_input_form:
                        user_input_form = import_user_input(bot_model_config.silly_character, user_name, bot.name)
                        bot_model_config.user_input_form = json.dumps(user_input_form)
                bot_model_config.bot_id = bot.id
                session.add(bot_model_config)
                session.commit()
                bot.bot_model_config_id = bot_model_config.id

        return bot

    @staticmethod
    def process_models(bot: Bot, user_id: str, import_data: dict):
        """
        Process embedding and chat models for the bot.
        """
        model_info_list = [
            *import_data.get("embedding_model_info", []),
            import_data.get("chat_model_info"),
        ]
        model_list = ModelService.get_model_list()
        model_map = {model.model_name: model for model in model_list}
        ollama_name_map = {model.ollama_model_name: model for model in model_list if model.ollama_model_name}

        for model_info in model_info_list:
            if not model_info:
                continue

            model_name = model_info["model_name"]
            provider = model_info.get("provider", OLLAMA_PROVIDER)
            ollama_name = model_info["ollama_model_name"]

            if model_name in model_map or ollama_name in ollama_name_map:
                if model_name not in model_map:
                    with db.session_scope() as session:
                        cur_model_config = (
                            session.query(BotModelConfig).filter_by(id=bot.bot_model_config_id).one_or_none()
                        )
                        if cur_model_config:
                            model_dict = cur_model_config.model_dict
                            if model_dict:
                                model_dict["name"] = ollama_name_map[ollama_name].model_name
                                cur_model_config.model = json.dumps(model_dict)
                continue

            provider_st = get_provider_setting(OLLAMA_PROVIDER)
            model_status = (
                DownloadStatus.ALL_COMPLETE
                if provider_st and provider_st.base_url and ollama_model_exist(provider_st.base_url, ollama_name)
                else DownloadStatus.DELETE
            )
            ModelService.create_new_model(
                model_name=model_name,
                provider=provider,
                ollama_model_name=ollama_name,
                user_id=user_id,
                source=model_info["source"],
                quantization_level=model_info["quantization_level"],
                modelfile=model_info["modelfile"],
                auto_modelfile=model_info["auto_modelfile"],
                use_xunlei=model_info["use_xunlei"],
                status=model_status,
            )

    @staticmethod
    def process_knowledge(bot: Bot, space_id: str, user_id: str, import_data: dict):
        """
        Process knowledge data and associated files for the bot.
        """
        knowledge_list = import_data.get("knowledge", [])
        agent_info = []

        if not knowledge_list:
            return

        for knowledge in knowledge_list:
            try:
                index_params = knowledge["index_params"]
                index_params.update({"metric_type": MILVUS_DISTANCE_METHOD})
                collection_name = CollectionDB.store_collection_info(
                    user_id=user_id,
                    knowledge_name=knowledge["knowledge_name"],
                    description=knowledge["knowledge_description"],
                    provider=knowledge.get("provider", OLLAMA_PROVIDER),
                    embedding_model=knowledge["embedding_model"],
                    similarity_threshold=knowledge["similarity_threshold"],
                    index_params=index_params,
                    chunk_size=knowledge.get("chunk_size", FILE_SETTINGS["CHUNK_SIZE"]),
                    chunk_overlap=knowledge.get("chunk_overlap", FILE_SETTINGS["CHUNK_OVERLAP"]),
                    top_k=knowledge.get("top_k", FILE_SETTINGS["TOP_K"]),
                    knowledge_status=DOCUMENTSTATUS.READY.value,
                )
                DocDB.create_new_doc(
                    space_id=space_id,
                    bot_id=bot.id,
                    description=bot.description,
                    user_id=user_id,
                    collection_name=collection_name,
                    embedding_model=knowledge["embedding_model"],
                )
                agent_info.append(
                    {
                        "description": knowledge["knowledge_description"],
                        "enabled": True,
                        "id": collection_name,
                        "name": knowledge["knowledge_name"],
                        "type": "dataset",
                    }
                )
                ImportBotService.process_knowledge_files(user_id, collection_name, knowledge["file_names"])

            except Exception as ex:
                logging.exception(f"Error processing knowledge entry {knowledge.get('knowledge_name', 'Unknown')}")
                continue

        with db.session_scope() as session:
            cur_data = session.query(BotModelConfig).filter_by(id=bot.bot_model_config_id).one_or_none()
            if cur_data:
                agent_mode_data = cur_data.agent_mode_dict
                agent_mode_data["tools"] = agent_info
                session.query(BotModelConfig).filter_by(id=bot.bot_model_config_id).update(
                    {BotModelConfig.agent_mode: json.dumps(agent_mode_data)}
                )

    @staticmethod
    def process_knowledge_files(user_id: str, collection_name: str, file_list: list):
        """
        Process and upload files associated with a knowledge item.
        """

        def fetch_file_from_url(url):
            """Download file content from a given URL with retry mechanism."""
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                return response.content
            except requests.exceptions.RequestException as e:
                logging.exception(f"Failed to download file from {url}")
                raise

        def save_uploaded_file(file: dict, file_content: bytes):
            """
            Upload a file and save its metadata to the database.
            """
            file_name = file["file_name"]
            file_type = file["file_type"]
            file_description = file["file_description"]

            try:
                # Upload the file
                result = upload_file(user_id=user_id, file_name=file_name, file_content=file_content)

                # Save metadata to the database
                with db.session_scope() as session:
                    doc = Document(
                        partition_name=f"d_{str(uuid.uuid4()).replace('-', '')}",
                        collection_name=collection_name,
                        file_id=result["file_id"],
                        file_name=file_name,
                        file_url=f"/api/documents/{result['file_id']}",
                        file_type=file_type,
                        description=file_description,
                        progress=0.0,
                        document_status=DOCUMENTSTATUS.READY.value,
                    )
                    session.add(doc)
                    logging.info(f"File {file_name} successfully uploaded and saved to the database.")
                    return doc
            except Exception as e:
                logging.exception(f"Failed to upload and save file {file_name}")
                raise

        try:
            for file_info in file_list:
                file_url = file_info.get("file_url")
                if file_url:
                    doc_content = fetch_file_from_url(file_url)
                    save_uploaded_file(file_info, doc_content)
        except Exception as ex:
            logging.exception("Error processing knowledge files")
            raise

    @staticmethod
    def process_tools(space_id: str, user_id: str, import_data: dict) -> dict:
        """
        Process and upload tool icon and other parameters.
        """

        return {}

    @staticmethod
    def load_yml_file(file_path: str) -> dict:
        """
        Load bot configuration from a YAML file.
        """
        if not os.path.isfile(file_path):
            raise ValidateError(f"File not found: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as yaml_file:
                return cast(dict, yaml.safe_load(yaml_file))
        except yaml.YAMLError as e:
            raise ValidateError("Invalid Bot file")

    @staticmethod
    def import_asset_from_url(user_id: str, asset_url: str, file_name: str, default_url: str = "") -> str:
        """
        Handle optional icon or background upload from a file path or download from a URL.
        """
        if not asset_url:
            return default_url

        # Download asset from URL
        try:
            response = requests.get(asset_url, timeout=10)
            response.raise_for_status()

            result = upload_file(user_id=user_id, file_name=file_name, file_content=response.content)
            return f"/api/documents/{result['file_id']}"
        except requests.RequestException as e:
            logging.exception("Failed to download icon from URL")
            return default_url
