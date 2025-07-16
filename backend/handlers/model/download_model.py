from configs.env import EXTERNAL_ARGO_PATH, USE_ARGO_OLLAMA
from configs.settings import USE_LOCAL_OLLAMA
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from core.model_providers.constants import OLLAMA_PROVIDER
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from models.model_manager import DownloadStatus
from services.model.model_service import ModelService


class DownloadModelHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["repo_id"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Download model
        description: Download model of the provided repository
        parameters:
          - in: body
            name: body
            description: Repo details
            schema:
              type: object
              required:
                - repo_id
              properties:
                repo_id:
                  type: string
                gguf_file:
                  type: string
                model_name:
                  type: string
                modelfile:
                  type: string
                quantization_level:
                  type: string
                  enum:
                    - f32
                    - f16
                    - bf16
                    - q8_0
                  default: f16
                use_xunlei:
                  type: boolean
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                model_info:
                  type: object
                  properties:
                    model_name:
                      type: string
                    source:
                      type: string
          400:
            description: Invalid input
          500:
            description: Process error
        """
        if USE_ARGO_OLLAMA != "true" and not EXTERNAL_ARGO_PATH and not USE_LOCAL_OLLAMA:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("model.url_download_no_support"),
                }
            )
            return

        source = self.req_dict.get("repo_id", "")
        if gguf_file := self.req_dict.get("gguf_file"):
            source = "/".join([source, gguf_file])
        if not (model_name := self.req_dict.get("model_name")):
            model_name = source.replace("/", "_").replace(".", "_")
        ollama_model_name = model_name + ":latest"

        category = self.req_dict.get("category", [])
        parameter = self.req_dict.get("parameter", "")
        model_list = ModelService.get_model_list()
        name_list = [model.model_name for model in model_list if model.download_status != DownloadStatus.DELETE]
        ollama_name_list = [
            model.ollama_model_name for model in model_list if model.download_status != DownloadStatus.DELETE
        ]

        if model_name in name_list or ollama_model_name in ollama_name_list:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeDuplicateOperate.value,
                    "msg": translation_loader.translation.t("model.duplicate_model_name"),
                }
            )
            return

        quantization_level = self.req_dict.get("quantization_level", "f16")
        modelfile = self.req_dict.get("modelfile", "")
        use_xunlei = self.req_dict.get("use_xunlei", False)

        model_template = ""
        # try:
        #     repo_info = HfApi().repo_info(source)
        #     repo_file_name_list = [f.rfilename for f in repo_info.siblings]
        #     if "tokenizer_config.json" in repo_file_name_list:
        #         file_url = huggingface_hub.hf_hub_url(source, "tokenizer_config.json")
        #         template = check_url(file_url)
        #         if template:
        #             model_template = generate_model_file(template)
        # except Exception as ex:
        #     logging.exception(ex)

        try:
            ModelService.create_new_model(
                model_name,
                OLLAMA_PROVIDER,
                ollama_model_name,
                self.current_user.id,
                source,
                category=category,
                parameter=parameter,
                quantization_level=quantization_level,
                modelfile=modelfile,
                auto_modelfile=model_template,
                use_xunlei=use_xunlei,
            )
            self.write(
                {
                    "errcode": Errcode.ErrcodeSuccess.value,
                    "model_info": {"model_name": model_name, "source": source},
                }
            )
        except Exception as ex:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeInternalServerError.value,
                    "msg": translation_loader.translation.t("model.model_download_task_failed", ex=ex),
                }
            )


api_router.add("/api/model/download_model", DownloadModelHandler)
