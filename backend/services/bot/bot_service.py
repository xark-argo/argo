import json
import logging
import os.path
import shutil
import time
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, cast
from urllib.parse import quote

import psutil
import requests
import yaml

from configs.env import (
    ARGO_STORAGE_PATH,
    ARGO_STORAGE_PATH_DOCUMENTS,
    ARGO_STORAGE_PATH_TEMP_BOT,
    FOLDER_TREE_FILE,
    MILVUS_DISTANCE_METHOD,
)
from configs.settings import FILE_SETTINGS
from core.entities.bot_entities import ProviderStatus
from core.errors.notfound import NotFoundError
from core.errors.validate import ValidateError
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_model_exist
from core.model_providers.utils import extract_base_provider
from core.tracking.client import BotTrackingPayload, argo_tracking
from database import db
from models.bot import (
    Bot,
    BotCategory,
    BotModelConfig,
    BotStatus,
    get_all_bot_by_space_id,
    get_bot,
    get_model_config,
)
from models.conversation import Conversation
from models.document import DOCUMENTSTATUS, Document
from models.model_manager import DownloadStatus, Model
from models.user import User, get_user
from services.bot.model_template import (
    char_model_templates,
    char_template,
    model_templates,
)
from services.bot.utils import (
    construct_silly_data,
    import_user_input,
    init_prompt,
    load_silly_card,
    save_silly_card,
    transform_input,
)
from services.common.provider_setting_service import create_provider_setting_from_info, get_provider_setting
from services.doc.doc_db import CollectionDB, DocDB, PartitionDB
from services.file.file_op import upload_file
from services.model.model_service import ModelService
from utils.gputil import get_gpus
from utils.path import app_path


class BotService:
    @staticmethod
    def create_bot(
        user: User,
        space_id: str,
        name: str,
        description: str,
        icon: str,
        category: str,
        background_img: Optional[str],
    ) -> Bot:
        mode = "chat"
        model_config_template = model_templates[mode + "_default"]
        if category == BotCategory.ROLEPLAY.value:
            model_config_template = char_model_templates[mode + "_default"]

        bot = Bot(**model_config_template["bot"])
        bot_model_config = BotModelConfig(**model_config_template["model_config"])

        bot.name = name
        bot.mode = mode
        bot.icon = icon
        bot.background_img = background_img
        bot.space_id = space_id
        bot.description = description
        bot.category = category
        bot.status = BotStatus.BOT_TO_BE_EDITED.value

        with db.session_scope() as session:
            session.add(bot)
            session.flush()

            if bot.category == BotCategory.ROLEPLAY.value:
                now = datetime.now()
                milliseconds = int(round(time.time() * 1000)) % 1000
                time_str = now.strftime("%Y-%m-%d @%Hh%Mm%Ss")
                char_template["chat"] = f"{char_template['name']} - {time_str}"
                time_str = now.strftime(f"%Y-%m-%d @%Hh %Mm %Ss {milliseconds}ms")
                char_template["create_date"] = time_str
                bot_model_config.silly_character = char_template
                bot_model_config.pre_prompt = init_prompt()
                user_input_form = import_user_input(bot_model_config.silly_character, user.username, bot.name)
                bot_model_config.user_input_form = json.dumps(user_input_form)

            bot_model_config.bot_id = bot.id
            session.add(bot_model_config)
            session.flush()

            bot.bot_model_config_id = bot_model_config.id
            session.commit()

        argo_tracking(BotTrackingPayload())
        return bot

    @staticmethod
    def list_bots(space_id: str):
        return get_all_bot_by_space_id(space_id)

    @staticmethod
    def get_bot_details(bot_id: str) -> tuple[Bot, BotModelConfig]:
        bot = get_bot(bot_id)
        if not bot:
            raise NotFoundError("Bot not found")

        model_config = get_model_config(bot.bot_model_config_id)
        if not model_config:
            raise NotFoundError("Bot model config not found")

        model_dict = json.loads(model_config.model)
        provider = model_dict.get("provider")
        if provider:
            icon_url = model_dict.get("icon_url", "")
            provider_info = create_provider_setting_from_info(provider, icon_url)
            model_dict.update(provider_info.model_dump(exclude_none=True, exclude_unset=True))
            model_config.model = json.dumps(model_dict)

        return bot, model_config
        # return {
        #     "id": bot.id,
        #     "name": bot.name,
        #     "description": bot.description,
        #     "mode": bot.mode,
        #     "icon": bot.icon,
        #     "background_img": bot.background_img,
        #     "category": bot.category,
        #     "locked": bot.locked,
        #     "model_config": model_config.to_dict(),
        #     "created_at": bot.created_at.isoformat(),
        # }

    @staticmethod
    def get_bots_info(bot_ids: list[str]) -> dict[str, Bot]:
        bots_info: dict[str, Bot] = {}
        if len(bot_ids) == 0:
            return bots_info

        with db.session_scope() as session:
            bots = session.query(Bot).filter(Bot.id.in_(bot_ids)).all()
            bots_info = {bot.id: bot for bot in bots}

        return bots_info

    @staticmethod
    def update_bot(
        bot_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        background_img: Optional[str] = None,
    ):
        with db.session_scope() as session:
            bot = session.get(Bot, bot_id)
            if not bot:
                raise ValueError("Bot not found")

            if name:
                bot.name = name
            if description:
                bot.description = description
            if icon:
                bot.icon = icon
            if background_img:
                bot.background_img = background_img

            session.commit()
            session.refresh(bot)
            return bot

    @staticmethod
    def delete_bot(space_id: str, bot_id: str):
        with db.session_scope() as session:
            bot = session.query(Bot).get(bot_id)
            if not bot:
                raise ValueError("Bot not found")

            session.query(BotModelConfig).filter_by(bot_id=bot_id).delete(synchronize_session=False)

            session.query(Conversation).filter_by(bot_id=bot_id).update({"is_deleted": True}, synchronize_session=False)

            session.delete(bot)
            session.commit()

    @staticmethod
    def share_bot(bot_id: str, user_id: str = "") -> dict:
        bot = get_bot(bot_id)
        if not bot:
            raise NotFoundError("Bot not found")

        model_config = get_model_config(bot.bot_model_config_id)
        if not model_config:
            raise NotFoundError("Bot model config not found")

        provider = model_config.model_dict.get("provider", OLLAMA_PROVIDER)
        model_dict = model_config.model_dict
        chat_model_name = model_dict.get("name")
        chat_model_info = ModelService.get_model_info(model_name=chat_model_name)
        if provider != OLLAMA_PROVIDER:
            chat_model_info = Model(model_name=chat_model_name, provider=provider)

        if not chat_model_info:
            raise NotFoundError("The Bot has no model configured and cannot be shared")
        if not chat_model_info.provider:
            chat_model_info.provider = OLLAMA_PROVIDER

        dataset_ids = BotService.get_dataset_ids_from_model_config(model_config)
        knowledge_list = [
            {
                "knowledge_name": knowledge.knowledge_name,
                "knowledge_description": knowledge.description,
                "provider": knowledge.provider,
                "embedding_model": knowledge.embedding_model,
                "index_params": knowledge.index_params,
                "similarity_threshold": knowledge.similarity_threshold,
                "file_names": [
                    {
                        "file_name": doc.file_name,
                        "file_type": doc.file_type,
                        "file_url": doc.file_url,
                        "real_file_name": doc.file_url.split("/")[-1],
                        "file_description": doc.description,
                    }
                    for doc in PartitionDB.get_documents_by_collection_name(collection_name=dataset_id)
                ],
            }
            for dataset_id in dataset_ids
            if (knowledge := CollectionDB.get_collection_by_name(collection_name=dataset_id))
        ]

        embedding_model_info = []
        seen_embedding_models = set()
        for item in knowledge_list:
            embedding_model = item["embedding_model"]
            provider = item.get("provider", OLLAMA_PROVIDER)

            key = f"{embedding_model}_{provider}"
            if key not in seen_embedding_models:
                cur_model_info = ModelService.get_model_info(model_name=embedding_model)
                if cur_model_info:
                    if not cur_model_info.provider:
                        cur_model_info.provider = OLLAMA_PROVIDER
                elif provider != OLLAMA_PROVIDER:
                    cur_model_info = Model(model_name=embedding_model, provider=provider)

                if cur_model_info:
                    embedding_model_info.append(cur_model_info.to_dict())
                    seen_embedding_models.add(key)

        final_model_config = model_config.to_dict()
        final_model_config.update({"user_input_form": transform_input(final_model_config.get("user_input_form", []))})

        icon_url = bot.icon
        if bot.category == BotCategory.ROLEPLAY.value:
            silly_config = construct_silly_data(model_config)
            if bot.icon.startswith("/api/documents"):
                real_icon_path = os.sep.join([ARGO_STORAGE_PATH_DOCUMENTS, bot.icon.split("/")[-1]])
                img_info = save_silly_card(
                    character_info=silly_config,
                    img_path=real_icon_path,
                    return_object=True,
                )
            else:
                conf_dir = app_path("resources", "icons")
                default_bot_image = os.sep.join([conf_dir, "bot.jpeg"])
                img_info = save_silly_card(
                    character_info=silly_config,
                    img_path=default_bot_image,
                    return_object=True,
                )
            result = upload_file(
                user_id=user_id,
                file_name="silly_char_tmp.png",
                file_content=img_info.getvalue(),
            )
            icon_url = f"/api/documents/{result['file_id']}"

        return {
            "name": bot.name,
            "icon": icon_url,
            "background_img": bot.background_img,
            "category": bot.category,
            "mode": bot.mode,
            "description": bot.description,
            "model_config": final_model_config,
            "knowledge": knowledge_list,
            "embedding_model_info": embedding_model_info,
            "chat_model_info": chat_model_info.to_dict(),
            "tool_info": [],
        }

    @staticmethod
    def export_bot(bot_id: str) -> tuple[str, str]:
        bot = get_bot(bot_id)
        if not bot:
            raise NotFoundError("Bot not found")

        model_config = get_model_config(bot.bot_model_config_id)
        if not model_config:
            raise NotFoundError("The Bot has no model configured and cannot be exported")

        model_json = json.loads(model_config.model)
        chat_model_name = model_json["name"]
        provider_name = model_json.get("provider", OLLAMA_PROVIDER)
        if provider_name == OLLAMA_PROVIDER:
            chat_model_info = ModelService.get_model_info(model_name=chat_model_name)
            if not chat_model_info:
                raise NotFoundError("The Bot has no model configured and cannot be exported")
            if not chat_model_info.provider:
                chat_model_info.provider = OLLAMA_PROVIDER
        else:
            chat_model_info = Model(model_name=chat_model_name, provider=provider_name)

        bot_config_path = os.sep.join([ARGO_STORAGE_PATH_TEMP_BOT, bot_id])
        if not os.path.exists(bot_config_path):
            os.mkdir(bot_config_path)

        silly_config = model_config.silly_character
        if bot.category == BotCategory.ROLEPLAY.value:
            silly_config = construct_silly_data(model_config)

        image_path = os.sep.join([bot_config_path, "icon.png"])
        real_icon_path = os.sep.join([ARGO_STORAGE_PATH_DOCUMENTS, bot.icon.split("/")[-1]])
        if os.path.exists(real_icon_path):
            if bot.category == BotCategory.ROLEPLAY.value:
                save_silly_card(silly_config, real_icon_path, image_path)
            else:
                fp_src_path = Path(real_icon_path)
                fp_tar_path = Path(image_path)

                with fp_src_path.open("rb") as fp_src, fp_tar_path.open("wb") as fp_tar:
                    fp_tar.write(fp_src.read())
        else:
            if bot.category == BotCategory.ROLEPLAY.value:
                conf_dir = app_path("resources", "icons")
                default_bot_image = os.sep.join([conf_dir, "bot.jpeg"])
                save_silly_card(silly_config, default_bot_image, image_path)
            else:
                conf_dir = Path(app_path("resources", "icons"))
                default_bot_image = conf_dir / "bot.jpeg"

                with (
                    Path(default_bot_image).open("rb") as fp_src,
                    Path(image_path).open("wb") as fp_tar,
                ):
                    fp_tar.write(fp_src.read())

        if bot.background_img:
            background_image_path = Path(bot_config_path) / "background_img.png"
            real_background_image_path = Path(ARGO_STORAGE_PATH_DOCUMENTS) / Path(bot.background_img).name

            if real_background_image_path.exists():
                with (
                    real_background_image_path.open("rb") as fp_src,
                    background_image_path.open("wb") as fp_tar,
                ):
                    fp_tar.write(fp_src.read())
            else:
                with background_image_path.open("wb") as fp_tar:
                    fp_tar.write(requests.get(bot.background_img).content)

        datasets = DocDB.get_datasets_by_bot_id(bot_id=bot_id)
        knowledge_list = []
        if len(datasets) > 0:
            for each_dataset in datasets:
                collection_name = each_dataset.collection_name
                knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
                if knowledge is None:
                    continue

                documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
                file_list = []
                for document in documents:
                    file_name = document.file_name
                    real_file_name = Path(ARGO_STORAGE_PATH_DOCUMENTS) / Path(document.file_url).name

                    if knowledge.folder:
                        folder_path = Path(knowledge.folder)
                        with (folder_path / FOLDER_TREE_FILE).open(encoding="utf-8") as fp:
                            tree_info = json.load(fp)
                        file_hash = Path(document.file_id).stem
                        if file_hash in tree_info:
                            real_file_name = Path(tree_info[file_hash])

                    if real_file_name.exists():
                        cur_file_path = Path(bot_config_path) / Path(document.file_url).name
                        with (
                            real_file_name.open("rb") as fp_src,
                            cur_file_path.open("wb") as fp_tar,
                        ):
                            fp_tar.write(fp_src.read())

                    file_list.append(
                        {
                            "file_name": file_name,
                            "file_type": document.file_type,
                            "real_file_name": Path(document.file_url).name,
                            "file_description": document.description,
                        }
                    )
                if len(file_list) > 0:
                    knowledge_list.append(
                        {
                            "knowledge_name": knowledge.knowledge_name,
                            "knowledge_description": knowledge.description,
                            "provider": knowledge.provider,
                            "embedding_model": knowledge.embedding_model,
                            "index_params": knowledge.index_params,
                            "similarity_threshold": knowledge.similarity_threshold,
                            "file_names": file_list,
                            "chunk_size": knowledge.chunk_size,
                            "chunk_overlap": knowledge.chunk_overlap,
                            "top_k": knowledge.top_k,
                        }
                    )

        embedding_model_info = []
        embedding_model_map = {}
        if knowledge_list:
            for each in knowledge_list:
                embedding_model = each["embedding_model"]
                if embedding_model in embedding_model_map:
                    continue
                cur_model_info = ModelService.get_model_info(model_name=embedding_model)
                if cur_model_info:
                    if not cur_model_info.provider:
                        cur_model_info.provider = OLLAMA_PROVIDER
                    embedding_model_info.append(cur_model_info.to_dict())
                    embedding_model_map[embedding_model] = True

        config_path = os.sep.join([bot_config_path, "config.yml"])
        final_model_config = model_config.to_dict()

        with open(config_path, "w", encoding="utf-8") as fp:
            yaml.dump(
                {
                    "bot": {
                        "name": bot.name,
                        "mode": bot.mode,
                        "description": bot.description,
                        "category": bot.category,
                    },
                    "model_config": final_model_config,
                    "knowledge": knowledge_list,
                    "embedding_model_info": embedding_model_info,
                    "chat_model_info": chat_model_info.to_dict(),
                    "tool_info": [],
                },
                fp,
                default_flow_style=False,
                allow_unicode=True,
            )

        zip_name = os.sep.join([ARGO_STORAGE_PATH_TEMP_BOT, f"{bot.name}.zip"])
        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as fp:
            for root, dirs, files in os.walk(bot_config_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    fp.write(file_path, os.path.relpath(file_path, bot_config_path))

        if os.path.exists(bot_config_path):
            shutil.rmtree(bot_config_path)
        return zip_name, quote(f"{bot.name}.zip")

    @staticmethod
    def import_bot(space_id: str, user_id: str, bot_file: str) -> Bot:
        with zipfile.ZipFile(bot_file) as fp:
            file_list = fp.namelist()
            if "config.yml" not in file_list:
                raise ValidateError("Invalid Bot file")
            try:
                with fp.open("config.yml") as yaml_file:
                    yaml_content = yaml_file.read()
                    import_data = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                raise ValidateError("Invalid Bot file")

            bot_data = import_data.get("bot")
            model_config_data = import_data.get("model_config")

            icon_content = None
            try:
                with fp.open("icon.png") as icon_file:
                    icon_content = icon_file.read()
                    result = upload_file(user_id=user_id, file_name="icon.png", file_content=icon_content)
                    icon = f"/api/documents/{result['file_id']}"
            except KeyError as ex:
                icon = ""

            try:
                with fp.open("background_img.png") as background_img_file:
                    background_img_content = background_img_file.read()
                    result = upload_file(
                        user_id=user_id,
                        file_name="background_img.png",
                        file_content=background_img_content,
                    )
                    background_img = f"/api/documents/{result['file_id']}"
            except KeyError as ex:
                background_img = ""

            category = bot_data.get("category", BotCategory.ASSISTANT.value)
            if not category:
                category = BotCategory.ASSISTANT.value
            if category == BotCategory.ROLEPLAY.value:
                buffer = BytesIO(icon_content or b"")
                character_info = load_silly_card(buffer)
                if not character_info:
                    raise ValidateError("Invalid SillyTavern png file")
                model_config_data["silly_character"] = character_info
            else:
                model_config_data["silly_character"] = {}

            bot = Bot(
                space_id=space_id,
                mode=bot_data.get("mode"),
                name=bot_data.get("name"),
                description=bot_data.get("description", ""),
                locked=bot_data.get("locked", False),
                category=category,
                icon=icon,
                background_img=background_img,
                status=BotStatus.BOT_UNINSTALL.value,
            )

            user = get_user(user_id)
            user_name = user.username
            with db.session_scope() as session:
                session.add(bot)
                session.commit()
                if model_config_data:
                    bot_model_config = BotModelConfig()
                    bot_model_config = bot_model_config.from_model_config_dict(model_config_data)
                    bot_model_config.tool_config = []
                    if category == BotCategory.ROLEPLAY.value:
                        if not bot_model_config.pre_prompt:
                            bot_model_config.pre_prompt = init_prompt()
                        if not bot_model_config.prologue:
                            bot_model_config.prologue = bot_model_config.silly_character.get("first_mes", "")
                        if not bot_model_config.user_input_form:
                            user_input_form = import_user_input(bot_model_config.silly_character, user_name, bot.name)
                            bot_model_config.user_input_form = json.dumps(user_input_form)
                    bot_model_config.bot_id = bot.id
                    session.add(bot_model_config)
                    session.commit()
                    bot.bot_model_config_id = bot_model_config.id

            model_info_list = [
                *import_data.get("embedding_model_info"),
                import_data.get("chat_model_info"),
            ]
            model_list = ModelService.get_model_list()
            model_map = {model.model_name: model for model in model_list}
            ollama_name_map = {model.ollama_model_name: model for model in model_list}

            for model_info in model_info_list:
                if model_info:
                    provider_name = model_info.get("provider", OLLAMA_PROVIDER)
                    if provider_name != OLLAMA_PROVIDER:
                        continue

                    if model_info["model_name"] in model_map or model_info["ollama_model_name"] in ollama_name_map:
                        if model_info["model_name"] not in model_map:
                            with db.session_scope() as session:
                                cur_model_config = (
                                    session.query(BotModelConfig).filter_by(id=bot.bot_model_config_id).one_or_none()
                                )
                                if cur_model_config:
                                    cur_model_json = json.loads(cur_model_config.model)
                                    cur_model_json["name"] = ollama_name_map[model_info["ollama_model_name"]].model_name
                                    model_str = json.dumps(cur_model_json)
                                    cur_model_config.model = model_str
                        continue

                    provider_st = get_provider_setting(OLLAMA_PROVIDER)
                    if (
                        provider_st
                        and provider_st.base_url
                        and ollama_model_exist(provider_st.base_url, model_info["ollama_model_name"])
                    ):
                        ModelService.create_new_model(
                            model_name=model_info["model_name"],
                            provider=OLLAMA_PROVIDER,
                            ollama_model_name=model_info["ollama_model_name"],
                            user_id=user_id,
                            source=model_info["source"],
                            size=model_info.get("size", 0),
                            quantization_level=model_info["quantization_level"],
                            modelfile=model_info["modelfile"],
                            auto_modelfile=model_info["auto_modelfile"],
                            use_xunlei=model_info["use_xunlei"],
                            status=DownloadStatus.ALL_COMPLETE,
                        )
                    else:
                        ModelService.create_new_model(
                            model_name=model_info["model_name"],
                            provider=OLLAMA_PROVIDER,
                            ollama_model_name=model_info["ollama_model_name"],
                            user_id=user_id,
                            source=model_info["source"],
                            size=model_info.get("size", 0),
                            quantization_level=model_info["quantization_level"],
                            modelfile=model_info["modelfile"],
                            auto_modelfile=model_info["auto_modelfile"],
                            use_xunlei=model_info["use_xunlei"],
                            status=DownloadStatus.DELETE,
                        )

            knowledge_list = import_data["knowledge"]
            agent_info = []
            if knowledge_list:
                for knowledge in knowledge_list:
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
                            "provider": knowledge.get("provider", OLLAMA_PROVIDER),
                            "enabled": True,
                            "id": collection_name,
                            "name": knowledge["knowledge_name"],
                            "type": "dataset",
                        }
                    )
                    file_list = knowledge["file_names"]
                    for each_file in file_list:
                        file = cast(dict, each_file)
                        try:
                            file_name = file["file_name"]
                            real_file_name = file["real_file_name"]
                            file_type = file["file_type"]
                            file_description = file["file_description"]
                            with fp.open(real_file_name) as current_doc:
                                doc_content = current_doc.read()
                                result = upload_file(
                                    user_id=user_id,
                                    file_name=file_name,
                                    file_content=doc_content,
                                )
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
                        except Exception as ex:
                            logging.exception("An error occurred while uploading file")
                            continue

                with db.session_scope() as session:
                    cur_data = model_config_data.get("agent_mode", {})
                    cur_data["tools"] = agent_info
                    cur_data_str = json.dumps(cur_data)
                    session.query(BotModelConfig).filter_by(id=bot.bot_model_config_id).update(
                        {BotModelConfig.agent_mode: cur_data_str}
                    )
            return bot

    @staticmethod
    def import_png_bot(space_id: str, user_id: str, bot_file: str) -> Bot:
        character_info = load_silly_card(bot_file)
        if not character_info:
            raise ValidateError("Invalid SillyTavern png file")

        try:
            icon_path = Path(bot_file)
            with icon_path.open("rb") as icon_file:
                icon_content = icon_file.read()
                result = upload_file(user_id=user_id, file_name="icon.png", file_content=icon_content)
                icon = f"/api/documents/{result['file_id']}"
        except OSError as ex:
            icon = ""

        name = ""
        if character_info.get("name", ""):
            name = character_info.get("name", "")
        elif character_info.get("data", {}).get("name", ""):
            name = character_info.get("data", {}).get("name", "")
        if isinstance(name, dict):
            name = json.dumps(name, ensure_ascii=False, indent=2)

        description = ""
        if character_info.get("creatorcomment", ""):
            description = character_info.get("creatorcomment", "")
        elif character_info.get("data", {}).get("creatorcomment", ""):
            description = character_info.get("data", {}).get("creatorcomment", "")
        elif character_info.get("creator_notes", ""):
            description = character_info.get("creator_notes", "")
        elif character_info.get("data", {}).get("creator_notes", ""):
            description = character_info.get("data", {}).get("creator_notes", "")
        if isinstance(description, dict):
            description = json.dumps(description, ensure_ascii=False, indent=2)

        mode = "chat"
        role_play_model_name = "mannix/gemma2-9b-simpo:q4_k_m"
        model_config_template = char_model_templates[mode + "_default"]
        model_json = json.loads(model_config_template["model_config"]["model"])
        model_json["name"] = role_play_model_name

        model_list = ModelService.get_model_list()
        model_map = {model.model_name: model for model in model_list}
        ollama_name_map = {model.ollama_model_name: model for model in model_list}
        if role_play_model_name in model_map or role_play_model_name in ollama_name_map:
            if role_play_model_name not in model_map:
                model_json["name"] = ollama_name_map[role_play_model_name].model_name
        else:
            provider_st = get_provider_setting(OLLAMA_PROVIDER)
            if provider_st and provider_st.base_url and ollama_model_exist(provider_st.base_url, role_play_model_name):
                ModelService.create_new_model(
                    model_name=role_play_model_name,
                    provider=OLLAMA_PROVIDER,
                    ollama_model_name=role_play_model_name,
                    user_id=user_id,
                    source="",
                    size=5761067609,
                    quantization_level="Q4_K_M",
                    modelfile="",
                    auto_modelfile="",
                    use_xunlei=False,
                    status=DownloadStatus.ALL_COMPLETE,
                )
            else:
                ModelService.create_new_model(
                    model_name=role_play_model_name,
                    provider=OLLAMA_PROVIDER,
                    ollama_model_name=role_play_model_name,
                    user_id=user_id,
                    source="",
                    size=5761067609,
                    quantization_level="Q4_K_M",
                    modelfile="",
                    auto_modelfile="",
                    use_xunlei=False,
                    status=DownloadStatus.DELETE,
                )

        model_config_template["model_config"]["model"] = json.dumps(model_json)
        bot = Bot(**model_config_template["bot"])
        bot_model_config = BotModelConfig(**model_config_template["model_config"])
        bot.space_id = space_id
        bot.mode = mode
        bot.name = name
        bot.description = description
        bot.category = BotCategory.ROLEPLAY.value
        bot.icon = icon
        bot.background_img = ""
        bot.status = BotStatus.BOT_UNINSTALL.value

        user = get_user(user_id)
        user_name = user.username
        with db.session_scope() as session:
            session.add(bot)
            session.commit()
            prompt = character_info.get("system_prompt", "")
            if not prompt:
                prompt = init_prompt()
            bot_model_config.pre_prompt = prompt

            first_mes = character_info.get("first_mes", "")
            if not first_mes:
                first_mes = character_info.get("data", {}).get("first_mes", "")
            alternate_greeting_list = character_info["data"].get("alternate_greetings", [])
            if not first_mes:
                while alternate_greeting_list:
                    item = alternate_greeting_list.pop()
                    if item:
                        first_mes = item
                        break
            character_info["data"]["alternate_greetings"] = alternate_greeting_list
            bot_model_config.silly_character = character_info
            bot_model_config.prologue = first_mes
            user_input_form = import_user_input(bot_model_config.silly_character, user_name, bot.name)
            bot_model_config.user_input_form = json.dumps(user_input_form)
            bot_model_config.bot_id = bot.id

            session.add(bot_model_config)
            session.commit()
            bot.bot_model_config_id = bot_model_config.id
        return bot

    @staticmethod
    def get_bot_detail(bot_id: str):
        bot = get_bot(bot_id)
        model_config = get_model_config(bot.bot_model_config_id)
        chat_model_info = {}
        if model_config:
            model_json = json.loads(model_config.model)
            chat_model_name = model_json["name"]
            provider_name = model_json.get("provider", OLLAMA_PROVIDER)

            if provider_name != OLLAMA_PROVIDER:
                chat_model_info = {
                    "model_name": chat_model_name,
                    "download_status": DownloadStatus.ALL_COMPLETE.value,
                }
                provider_st = get_provider_setting(provider_name)
                if provider_st:
                    support_models = [
                        each_model.model for each_model in provider_st.support_chat_models
                    ] + provider_st.custom_chat_models
                if not provider_st or (
                    provider_st and (chat_model_name not in support_models or provider_st.enable != 1)
                ):
                    chat_model_info["provider_status"] = ProviderStatus.NOT_INIT.value
                    chat_model_info["download_status"] = DownloadStatus.DOWNLOADING.value
                else:
                    chat_model_info["provider_status"] = ProviderStatus.AVAILABLE.value
                chat_model_info["provider"] = extract_base_provider(provider_name)
            else:
                provider_st = get_provider_setting(provider=OLLAMA_PROVIDER)
                base_url = provider_st.base_url or "" if provider_st else ""

                remote = False
                if not ("localhost" in base_url or "127.0.0.1" in base_url):
                    remote = True
                chat_model = ModelService.get_model_info(chat_model_name)
                if chat_model is None:
                    chat_model_info = {}
                else:
                    total_size = chat_model.size
                    message = ""
                    if not remote:
                        if total_size:
                            _, _, free_b, _ = psutil.disk_usage(ARGO_STORAGE_PATH)
                            free_gb = free_b / (1024**3)
                            # _, _, free_gb = ps.get_disk_usage(ARGO_STORAGE_PATH)
                            total_size_gb = total_size / (1024**3)
                            if total_size_gb > free_gb:
                                message = translation_loader.translation.t(
                                    "model.insufficient_disk",
                                    total_size_gb=f"{total_size_gb:.2f}",
                                    free_gb=f"{free_gb:.2f}",
                                )
                            else:
                                total_gpu_memory_gb = sum(gpu_info.memory_total for gpu_info in get_gpus()) / 1024
                                total_memory_b = psutil.virtual_memory().total
                                total_memory_gb = total_memory_b / (1024**3)
                                # total_memory_gb, _ = ps.system_memory_usage()
                                system_memory_gb = total_gpu_memory_gb + total_memory_gb - 1.0
                                if system_memory_gb < total_size_gb:
                                    message = translation_loader.translation.t(
                                        "model.insufficient_memory",
                                        total_size_gb=f"{total_size_gb:.2f}",
                                        free_gb=f"{system_memory_gb:.2f}",
                                    )
                    if "complete" not in chat_model.download_status.value and message:
                        chat_model_info = {
                            "model_name": chat_model.model_name,
                            "download_status": DownloadStatus.INCOMPATIBLE.value,
                            "download_speed": chat_model.download_speed,
                            "download_progress": chat_model.download_progress,
                            "process_message": message,
                        }
                    else:
                        chat_model_info = {
                            "model_name": chat_model.model_name,
                            "download_status": chat_model.download_status.value,
                            "download_speed": chat_model.download_speed,
                            "download_progress": chat_model.download_progress,
                            "process_message": chat_model.process_message,
                        }

        datasets = DocDB.get_datasets_by_bot_id(bot_id=bot_id)
        knowledge_info_list = []
        embedding_model_info_list = []
        embedding_model_list = []
        for each_dataset in datasets:
            collection_name = each_dataset.collection_name
            knowledge = CollectionDB.get_collection_by_name(collection_name=collection_name)
            if knowledge is None:
                continue

            embedding_model_list.append((knowledge.embedding_model, knowledge.provider))
            documents = PartitionDB.get_documents_by_collection_name(collection_name=collection_name)
            if len(documents) == 0:
                knowledge_progress = 1.0
            else:
                if len(documents) == 1:
                    knowledge_progress = documents[0].progress
                else:
                    knowledge_progress = sum(1 / (len(documents) + 0.0) * document.progress for document in documents)
            if knowledge is None:
                continue
            else:
                knowledge_info_list.append(
                    {
                        "knowledge_name": knowledge.knowledge_name,
                        "knowledge_progress": knowledge_progress,
                        "knowledge_status": knowledge.knowledge_status,
                        "embedding_model": knowledge.embedding_model,
                        "collection_name": knowledge.collection_name,
                    }
                )

        embedding_model_list = list(set(embedding_model_list))
        for embedding_model, provider_name in embedding_model_list:
            if provider_name and provider_name != OLLAMA_PROVIDER:
                embedding_model_info = {
                    "model_name": embedding_model,
                    "provider": provider_name,
                    "download_status": DownloadStatus.ALL_COMPLETE.value,
                }

                provider_st = get_provider_setting(provider_name)
                if provider_st:
                    support_embedding_models = [
                        each_model.model for each_model in provider_st.support_embedding_models
                    ] + provider_st.custom_embedding_models
                if not provider_st or (provider_st and embedding_model not in support_embedding_models):
                    embedding_model_info["provider_status"] = ProviderStatus.NOT_INIT.value
                    embedding_model_info["download_status"] = DownloadStatus.DOWNLOADING.value
                else:
                    embedding_model_info["provider_status"] = ProviderStatus.AVAILABLE.value
                embedding_model_info["provider"] = extract_base_provider(provider_name)

                embedding_model_info_list.append(embedding_model_info)
                continue

            embed_model = ModelService.get_model_info(embedding_model)
            if embed_model is None:
                continue
            else:
                embedding_model_info = {
                    "model_name": embed_model.model_name,
                    "download_status": embed_model.download_status.value,
                    "download_speed": embed_model.download_speed,
                    "download_progress": embed_model.download_progress,
                    "process_message": embed_model.process_message,
                    "provider": provider_name,
                }
                embedding_model_info_list.append(embedding_model_info)
        return {
            "chat_model_info": chat_model_info,
            "embedding_model_info_list": embedding_model_info_list,
            "knowledge_info_list": knowledge_info_list,
        }

    @staticmethod
    def get_all_bots():
        with db.session_scope() as session:
            bots = session.query(Bot).all()
            return bots

    @staticmethod
    def get_dataset_ids_from_model_config(bot_model_config: BotModelConfig) -> set:
        dataset_ids: set[str] = set()
        if not bot_model_config:
            return dataset_ids

        agent_mode = bot_model_config.agent_mode_dict
        if not agent_mode.get("tools"):
            return dataset_ids

        tools = agent_mode.get("tools", [])
        for tool in tools:
            if tool.get("enabled") is False:
                continue
            tool_type = tool.get("type")
            if tool_type == "dataset":
                dataset_ids.add(tool.get("id"))

        return dataset_ids
