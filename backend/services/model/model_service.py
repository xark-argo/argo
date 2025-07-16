import logging
import textwrap
from datetime import datetime
from typing import Any, Optional

from core.entities.model_entities import APIModelCategory
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.ollama.ollama_api import ollama_create_model
from core.tracking.client import ModelTrackingPayload, argo_tracking
from database.db import session_scope
from models.model_manager import DownloadStatus, Model
from services.common.provider_setting_service import get_provider_setting
from services.model.modelfile_parser import parse_modelfile
from services.model.utils import is_parameters_equal


class ModelService:
    @staticmethod
    def create_new_model(
        model_name,
        provider,
        ollama_model_name,
        user_id,
        source,
        *,
        description: str = "",
        category: list[str] = [],
        parameter: str = "",
        size: int = 0,
        quantization_level: Optional[str] = None,
        modelfile: Optional[str] = None,
        auto_modelfile: Optional[str] = None,
        status: Optional[DownloadStatus] = None,
        use_xunlei: bool = False,
    ):
        with session_scope() as session:
            model_list = session.query(Model).filter(Model.model_name == model_name).all()
            for model in model_list:
                if model.download_status == DownloadStatus.DELETE:
                    session.delete(model)
            logging.info(f"model_list: {[each.model_name for each in model_list]}")

        with session_scope() as session:
            ollama_model_list = session.query(Model).filter(Model.ollama_model_name == ollama_model_name).all()
            for model in ollama_model_list:
                if model.download_status == DownloadStatus.DELETE:
                    session.delete(model)
            logging.info(f"ollama_model_list: {[each.model_name for each in ollama_model_list]}")

        is_embeddings = APIModelCategory.EMBEDDING.value in category
        is_generation = not is_embeddings
        with session_scope() as session:
            all_models = session.query(Model).all()
            logging.info(f"all_models: {[each.model_name for each in all_models]}")
            model = Model(
                model_name=model_name,
                provider=provider,
                ollama_model_name=ollama_model_name,
                source=source,
                created_by=user_id,
                updated_by=user_id,
                description=description,
                category=category,
                parameter=parameter,
                is_embeddings=is_embeddings,
                is_generation=is_generation,
            )
            if size:
                model.size = size
            if quantization_level:
                model.quantization_level = quantization_level
            # 创建模型不再支持modelfile @v0.2.6 需求
            # if modelfile:
            #     model.modelfile = modelfile
            if auto_modelfile:
                model.auto_modelfile = auto_modelfile
            if status:
                model.download_status = status
            if use_xunlei:
                model.use_xunlei = use_xunlei
            session.add(model)

        argo_tracking(
            ModelTrackingPayload(
                model_name=source or "",
                model_provider=model.provider or "",
                status=DownloadStatus.DOWNLOAD_WAITING.value,
            )
        )

    @staticmethod
    def get_model_info(model_name) -> Optional[Model]:
        with session_scope() as session:
            model = session.query(Model).filter(Model.model_name == model_name).one_or_none()
        return model

    @staticmethod
    def get_model_list(
        *,
        status: Optional[DownloadStatus] = None,
        is_generation: bool = False,
        is_embeddings: bool = False,
    ):
        with session_scope() as session:
            query = session.query(Model)
            if status:
                query = query.filter(Model.download_status == status)
            if is_generation:
                query = query.filter(Model.is_generation == is_generation)
            if is_embeddings:
                query = query.filter(Model.is_embeddings == is_embeddings)
            model_list = query.all()

        return model_list

    @staticmethod
    def get_undelete_model_list():
        with session_scope() as session:
            model_list = session.query(Model).filter(Model.download_status != DownloadStatus.DELETE).all()
            return model_list

    @staticmethod
    def update_model_status(
        model_name,
        download_status,
        *,
        download_progress=0,
        download_speed=0,
        ollama_template=None,
        ollama_parameters=None,
        process_message="",
        download_info=None,
        category=None,
        reset=False,
        is_embeddings=None,
        is_generation=None,
    ):
        with session_scope() as session:
            if model := session.query(Model).filter(Model.model_name == model_name).one_or_none():
                if not reset:
                    model.download_status = download_status
                if is_embeddings is not None:
                    model.is_embeddings = is_embeddings
                if is_generation is not None:
                    model.is_generation = is_generation
                if download_status == DownloadStatus.DELETE:
                    model.digest = ""
                if download_progress is not None:
                    model.download_progress = download_progress
                if category is not None:
                    model.category = category
                if process_message:
                    model.process_message = process_message
                if download_speed is not None:
                    model.download_speed = download_speed
                if ollama_template is not None:
                    model.ollama_template = ollama_template
                if ollama_parameters is not None:
                    model.ollama_parameters = ollama_parameters
                if download_info:
                    model.download_info = download_info
                if download_status in [
                    DownloadStatus.DOWNLOAD_FAILED,
                    DownloadStatus.CONVERT_FAILED,
                    DownloadStatus.IMPORT_FAILED,
                    DownloadStatus.ALL_COMPLETE,
                ]:
                    argo_tracking(
                        ModelTrackingPayload(
                            model_name=model.source or "",
                            model_provider=model.provider or "",
                            status=download_status.value,
                            message=process_message or "",
                        )
                    )
                if reset and model.download_status in [
                    DownloadStatus.DELETE,
                    DownloadStatus.DOWNLOAD_PAUSE,
                ]:
                    model.download_speed = 0
                    return False
                return True
        return False

    @staticmethod
    def update_ollama_modelfile_and_reload_model(model_name: str, modelfile_content: str):
        if not modelfile_content or not model_name:
            return

        try:
            modelfile = parse_modelfile(modelfile_content, True)
            request = modelfile.create_request()
        except Exception as e:
            preview = textwrap.shorten(modelfile_content, width=100, placeholder="...")
            logging.exception(f"Failed to parse modelfile (preview: {preview})")
            raise ValueError(f"Invalid modelfile format: {e}")

        if not request or not request.template:
            logging.info("Parsed modelfile contains no template. Skipping.")
            return

        chat_template = request.template
        parameters = request.parameters

        with session_scope() as session:
            model = session.query(Model).filter(Model.model_name == model_name).one_or_none()
            if not model:
                raise ValueError(f"Model '{model_name}' not found.")
            if not model.ollama_model_name:
                raise ValueError(f"Model '{model_name}' has no associated Ollama model name.")
            if model.provider != OLLAMA_PROVIDER:
                raise ValueError(f"Model '{model_name}' is not provided by Ollama.")
            if model.download_status != DownloadStatus.ALL_COMPLETE:
                raise RuntimeError(f"Model '{model_name}' is not fully downloaded.")

            if model.ollama_template == chat_template and is_parameters_equal(model.ollama_parameters, parameters):
                logging.info(f"Chat template and parameters unchanged for model '{model_name}'.")
                return

            old_status = model.download_status
            old_ollama_template = model.ollama_template
            old_ollama_parameters = model.ollama_parameters

            model.ollama_template = chat_template
            model.ollama_parameters = parameters
            model.download_status = DownloadStatus.IMPORT_COMPLETE
            session.commit()

        try:
            provider_st = get_provider_setting(OLLAMA_PROVIDER)
            if not provider_st:
                raise ValueError(f"Provider '{OLLAMA_PROVIDER}' is not initialized")

            ollama_create_model(
                base_url=provider_st.safe_base_url,
                model_name=model.ollama_model_name,
                from_=model.ollama_model_name,
                template=model.ollama_template,
                parameters=model.ollama_parameters,
            )
        except Exception as e:
            logging.warning(f"Rolling back model '{model_name}' to previous state due to error: {e}")
            ModelService.update_model_status(
                model_name,
                old_status,
                ollama_template=old_ollama_template,
                ollama_parameters=old_ollama_parameters,
            )
            raise e

    @staticmethod
    def update_model_name(
        model_name,
        user_id,
        new_model_name,
        description,
        status: Optional[DownloadStatus] = None,
    ):
        with session_scope() as session:
            if model := session.query(Model).filter(Model.model_name == model_name).one_or_none():
                if new_model_name:
                    model.model_name = new_model_name
                if description:
                    model.description = description
                if status:
                    model.download_status = status
                model.updated_by = user_id
                return True
        return False

    @staticmethod
    def sync_model_info(
        model_name,
        digest,
        category,
        parameter,
        size,
        model_fmt,
        quantization_level,
        is_generation,
        is_embeddings,
        *,
        ollama_template: Optional[str] = None,
        ollama_architecture: Optional[str] = None,
        ollama_parameters: Optional[dict[str, Any]] = None,
        created_at=None,
        status: Optional[DownloadStatus] = None,
    ) -> bool:
        if created_at is None:
            created_at = datetime.now()
        with session_scope() as session:
            if model := session.query(Model).filter(Model.model_name == model_name).one_or_none():
                model.digest = digest
                model.category = category or []
                model.parameter = parameter or ""
                model.size = size
                model.model_fmt = model_fmt
                model.quantization_level = quantization_level
                model.is_generation = is_generation
                model.is_embeddings = is_embeddings
                model.ollama_template = ollama_template
                model.ollama_architecture = ollama_architecture
                model.ollama_parameters = ollama_parameters
                if status:
                    model.download_status = status
                model.created_at = created_at
                return True
        return False

    @staticmethod
    def update_model_info(
        model_name: str,
        ollama_template: Optional[str] = None,
        ollama_architecture: Optional[str] = None,
        ollama_parameters: Optional[dict[str, Any]] = None,
    ) -> Optional[Model]:
        with session_scope() as session:
            model = session.query(Model).filter(Model.model_name == model_name).one_or_none()
            if not model:
                return None

            model.ollama_template = ollama_template
            model.ollama_architecture = ollama_architecture
            model.ollama_parameters = ollama_parameters
            session.commit()

            return model

    @staticmethod
    def delete_model(model_name):
        with session_scope() as session:
            if model := session.query(Model).filter(Model.model_name == model_name).one_or_none():
                session.delete(model)
                argo_tracking(
                    ModelTrackingPayload(
                        model_name=model.source or "",
                        model_provider=model.provider or "",
                        status=DownloadStatus.DELETE.value,
                    )
                )
                return True
        return False
