import logging
import operator
from concurrent.futures import ThreadPoolExecutor

from tornado.concurrent import run_on_executor

from core.entities.model_entities import APIModelCategory
from core.errors.errcode import Errcode
from core.model_providers.constants import OLLAMA_PROVIDER
from core.model_providers.model_category_style import get_model_style
from core.model_providers.ollama.ollama_api import ollama_alive
from database.provider_store import get_provider_settings_from_db
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.common.provider_setting_service import get_all_provider_settings
from services.model.model_service import ModelService
from services.model.utils import build_ollama_modelfile


class GetModelListHandler(BaseProtectedHandler):
    executor = ThreadPoolExecutor(max_workers=10)

    @run_on_executor
    def post(self):
        """
        ---
        tags:
          - Model
        summary: Get model list
        description: Get all model list
        parameters:
          - in: body
            name: body
            description: Model Status details
            schema:
              type: object
              properties:
                is_generation:
                  type: boolean
                is_embeddings:
                  type: boolean
                download_status:
                  type: string
                  enum:
                    - download_waiting
                    - downloading
                    - download_complete
                    - convert_complete
                    - import_complete
                    - all_complete
                    - download_failed
                    - convert_failed
                    - import_failed
                    - not_available
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                model_list:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: string
                      model_name:
                        type: string
                      ollama_model_name:
                        type: string
                      ollama_architecture:
                        type: string
                      modelfile_content:
                        type: string
                      digest:
                        type: string
                      source:
                        type: string
                      description:
                        type: string
                      category:
                        type: array
                        items:
                          type: string
                      parameter:
                        type: string
                      size:
                        type: integer
                      model_fmt:
                        type: string
                      quantization_level:
                        type: string
                      is_generation:
                        type: boolean
                      is_embeddings:
                        type: boolean
                      download_status:
                        type: string
                        enum:
                          - download_waiting
                          - downloading
                          - download_complete
                          - convert_complete
                          - import_complete
                          - all_complete
                          - download_failed
                          - convert_failed
                          - import_failed
                          - not_available
                      download_speed:
                        type: integer
                      download_progress:
                        type: integer
                      download_info:
                        type: object
                        additionalProperties:
                          type: string
                      process_message:
                        type: string
                      updated_at:
                        type: integer
                      created_at:
                        type: integer
          400:
            description: Invalid input
          500:
            description: Process error
        """
        download_status_string = self.req_dict.get("download_status", "")
        is_generation = self.req_dict.get("is_generation", False)
        is_embeddings = self.req_dict.get("is_embeddings", False)

        download_status = DownloadStatus.__members__.get(download_status_string.upper())
        provider_st = get_provider_settings_from_db(provider=OLLAMA_PROVIDER)

        flag = False
        if provider_st:
            base_url = provider_st["base_url"]
            try:
                _ = ollama_alive(base_url)
                flag = True
            except Exception as ex:
                logging.warning(f"Ollama service is not available. error: {ex}")

        sorted_model_list = []
        if flag:
            model_list = ModelService.get_model_list(
                status=download_status,
                is_generation=is_generation,
                is_embeddings=is_embeddings,
            )
            model_list = [model for model in model_list if model.download_status != DownloadStatus.DELETE]
            res_model_list = [
                {
                    "id": model.id,
                    "model_name": model.model_name,
                    "ollama_model_name": model.ollama_model_name,
                    "modelfile_content": (
                        build_ollama_modelfile(
                            ollama_template=model.ollama_template,
                            ollama_parameters=model.ollama_parameters,
                        )
                        if model.ollama_template
                        else ""
                    ),
                    "ollama_parameters": model.ollama_parameters,
                    "ollama_architecture": model.ollama_architecture,
                    "provider": OLLAMA_PROVIDER,
                    "digest": model.digest,
                    "source": model.source,
                    "color": "#DBF3E4",
                    "icon_url": "/api/files/resources/icons/ollama.png",
                    "description": model.description,
                    "category": {
                        "extra_label": (
                            []
                            if model.category is None
                            else [
                                each
                                for each in model.category
                                if each not in [category.value for category in APIModelCategory]
                            ]
                        ),
                        "category_label": {
                            "type": (
                                APIModelCategory.EMBEDDING.value
                                if (model.category and APIModelCategory.EMBEDDING.value in model.category)
                                else APIModelCategory.CHAT.value
                            ),
                            "category": (
                                []
                                if model.category is None
                                else [
                                    get_model_style(each)
                                    for each in model.category
                                    if each
                                    in [
                                        APIModelCategory.TOOLS.value,
                                        APIModelCategory.EMBEDDING.value,
                                        APIModelCategory.VISION.value,
                                    ]
                                ]
                            ),
                        },
                    },
                    "parameter": model.parameter or "",
                    "size": model.size,
                    "model_fmt": model.model_fmt,
                    "quantization_level": model.quantization_level,
                    "is_generation": model.is_generation,
                    "is_embeddings": model.is_embeddings,
                    "download_status": model.download_status.value,
                    "download_speed": model.download_speed,
                    "download_progress": model.download_progress,
                    "download_info": model.download_info,
                    "process_message": model.process_message,
                    "updated_at": int(model.updated_at.timestamp()),
                    "created_at": int(model.created_at.timestamp()),
                }
                for model in model_list
            ]
            sorted_model_list = sorted(res_model_list, key=operator.itemgetter("model_name"))

        provider_model_list = []
        provider_list = get_all_provider_settings()
        # 如果is_generation和is_embeddings都为False 返回全部模型
        all = not is_generation and not is_embeddings

        for providerSt in provider_list:
            if providerSt.provider == OLLAMA_PROVIDER:
                continue
            if providerSt.enable != 1:
                continue

            if all or is_generation:
                for modelInfo in providerSt.support_chat_models:
                    provider_model_list.append(
                        {
                            "id": providerSt.provider + "/" + modelInfo.model,
                            "model_name": modelInfo.model,
                            "provider": providerSt.provider,
                            "color": providerSt.color,
                            "icon_url": providerSt.icon_url,
                            "is_generation": True,
                            "is_embeddings": False,
                            "category": {
                                "extra_label": [],
                                "category_label": {
                                    "type": APIModelCategory.CHAT.value,
                                    "category": [
                                        get_model_style(each)
                                        for each in modelInfo.tags
                                        if each
                                        in [
                                            APIModelCategory.TOOLS.value,
                                            APIModelCategory.VISION.value,
                                        ]
                                    ],
                                },
                            },
                            "parameter": "latest",
                        }
                    )

            if all or is_embeddings:
                for modelInfo in providerSt.support_embedding_models:
                    provider_model_list.append(
                        {
                            "id": providerSt.provider + "/" + modelInfo.model,
                            "model_name": modelInfo.model,
                            "provider": providerSt.provider,
                            "color": providerSt.color,
                            "icon_url": providerSt.icon_url,
                            "is_generation": False,
                            "is_embeddings": True,
                            "category": {
                                "extra_label": [],
                                "category_label": {
                                    "type": APIModelCategory.EMBEDDING.value,
                                    "category": [
                                        get_model_style(each)
                                        for each in modelInfo.tags
                                        if each == APIModelCategory.EMBEDDING.value
                                    ],
                                },
                            },
                            "parameter": "latest",
                        }
                    )

        sorted_model_list += provider_model_list
        self.write(
            {
                "errcode": Errcode.ErrcodeSuccess.value,
                "model_list": sorted_model_list,
                "recommend_model": {
                    "embedding_model": {
                        "model_name": "bge-m3",
                        "provider": "ollama",
                        "user_id": self.current_user.id,
                        "description": "BGE-M3 is a new model from BAAI distinguished for its versatility in \
                        Multi-Functionality, Multi-Linguality, and Multi-Granularity.",
                        "category": {
                            "extra_label": [],
                            "category_label": {
                                "type": "embedding",
                                "category": [get_model_style(APIModelCategory.EMBEDDING.value)],
                            },
                        },
                        "parameter": "567m",
                    }
                },
            }
        )


api_router.add("/api/model/get_model_list", GetModelListHandler)
