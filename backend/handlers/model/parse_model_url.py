# import logging
import re

# import huggingface_hub
import requests
from bs4 import BeautifulSoup

from configs.env import EXTERNAL_ARGO_PATH, USE_ARGO_OLLAMA
from configs.settings import USE_LOCAL_OLLAMA
from core.errors.errcode import Errcode
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router
from services.doc.util import random_ua

# from services.model.convert import judge_model_architecture
from utils.network import is_china_network
from utils.size_utils import convert_bits, size_transfer

http_session = requests.session()


class ParseModelUrlHandler(BaseProtectedHandler):
    def __init__(self, *args):
        super().__init__(*args)
        self.required_fields = ["repo"]

    def post(self):
        """
        ---
        tags:
          - Model
        summary: Parse model url
        description: Parse model information of the provided url
        parameters:
          - in: body
            name: body
            description: Url details
            schema:
              type: object
              required:
                - repo
              properties:
                repo:
                  type: string
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                repo_id:
                  type: string
                model_template:
                  type: string
                warning_msg:
                  type: string
                repo_file_list:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                       type: string
                      size:
                       type: integer
                gguf_file_list:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                       type: string
                      size:
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

        source = self.req_dict.get("repo", "")
        repo_id = self.parse_repo_id(source)
        if not repo_id:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeParseFailed.value,
                    "msg": translation_loader.translation.t("model.only_support_huggingface_repo"),
                }
            )
            return

        is_china = is_china_network()
        base_url = f"https://huggingface.co/{repo_id}/tree/main"
        if is_china:
            base_url = f"https://hf-mirror.com/{repo_id}/tree/main"

        parameter = ParseModelUrlHandler.extract_model_size(repo_id)
        model_total_size = 0.0
        repo_file_list = []
        repo_file_name_list = []
        category = []
        try:
            content = requests.get(
                base_url,
                headers={
                    "User-Agent": random_ua(),
                },
            ).content.decode("utf-8")
            if "Not-For-All-Audiences" in content:
                base_url = f"{base_url}?not-for-all-audiences=true"
                content = requests.get(
                    base_url,
                    headers={
                        "User-Agent": random_ua(),
                    },
                ).content.decode("utf-8")
            soup = BeautifulSoup(content, "html.parser")
            category_labels = soup.find_all(["a", "button"], class_=re.compile("^rounded-lg"))
            for each_label in category_labels:
                href = each_label.get("href", None)
                if href is None or "pipeline_tag" in href or "language" in href:
                    category.append(each_label.span.text)
                elif "other=text-embeddings-inference" in href:
                    category.append("embedding")
                elif "other=tool-use" in href:
                    category.append("tool")
            if "embedding" not in category and "embed" in base_url:
                category.append("embedding")
            ul = soup.find("ul", class_=re.compile("^mb-8"))
            li = ul.find_all("li", class_=re.compile("^relative grid"))
            for each in li:
                div = each.find("div")
                file_name = div.find("a").find("span").get_text()
                size = div.find_next_sibling("a").find("span").get_text()
                size = size_transfer(size)
                repo_file_list.append({"name": file_name, "size": convert_bits(size)})
                repo_file_name_list.append(file_name)
                model_total_size += size
        except Exception as ex:
            self.set_status(500)
            self.write(
                {
                    "errcode": Errcode.ErrcodeParseFailed.value,
                    "msg": translation_loader.translation.t("model.get_repo_info_failed", ex=ex),
                }
            )
            return

        warning_msg = ""
        # Todo: for local model gpu memory check, need to be implemented if local model is important
        # allocated, cached, total = ps.system_gpu_memory()
        # logging.info(f"System GPU memory: allocated: {allocated}MB, cached: {cached}MB, total: {total}MB")
        # free = total - allocated if total else 0
        # if free and model_total_size / (1024**3) > free:
        #     warning_msg = "Will be slow on your device"

        gguf_file_list = [file for file in repo_file_list if file["name"].endswith(".gguf")]
        if len(gguf_file_list) > 0:
            self.write(
                {
                    "errcode": Errcode.ErrcodeSuccess.value,
                    "repo_id": repo_id,
                    "model_template": "",
                    "gguf_file_list": gguf_file_list,
                    "parameter": parameter,
                    "category": category,
                    "warning_msg": warning_msg,
                }
            )
            return

        # not support safetensors model
        self.set_status(500)
        self.write(
            {
                "errcode": Errcode.ErrcodeParseFailed.value,
                "msg": translation_loader.translation.t(
                    "model.architecture_not_supported",
                    architecture="safetensors_model_file",
                ),
            }
        )
        return

        # if "config.json" not in repo_file_name_list:
        #     self.set_status(500)
        #     self.write(
        #         {
        #             "errcode": Errcode.ErrcodeParseFailed.value,
        #             "msg": translation_loader.translation.t("model.config_json_not_found"),
        #         }
        #     )
        #     return

        # try:
        #     config_url = huggingface_hub.hf_hub_url(repo_id, "config.json")
        #     model_config = http_session.get(config_url).json()
        #     if "architectures" not in model_config or len(model_config.get("architectures")) == 0:
        #         self.set_status(500)
        #         self.write(
        #             {
        #                 "errcode": Errcode.ErrcodeParseFailed.value,
        #                 "msg": "Model config.json invalid, cannot parse architectures! Please check!",
        #             }
        #         )
        #         return
        #     architecture = model_config.get("architectures")[0]

        #     if judge_model_architecture(architecture):
        #         self.write(
        #             {
        #                 "errcode": Errcode.ErrcodeSuccess.value,
        #                 "repo_id": repo_id,
        #                 "model_template": "",
        #                 "repo_file_list": repo_file_list,
        #                 "parameter": parameter,
        #                 "category": category,
        #                 "warning_msg": warning_msg,
        #             }
        #         )
        #         return
        #     else:
        #         self.set_status(500)
        #         self.write(
        #             {
        #                 "errcode": Errcode.ErrcodeParseFailed.value,
        #                 "msg": translation_loader.translation.t(
        #                     "model.architecture_not_supported",
        #                     architecture=architecture,
        #                 ),
        #             }
        #         )
        #         return
        # except Exception as ex:
        #     self.set_status(500)
        #     self.write(
        #         {
        #             "errcode": Errcode.ErrcodeParseFailed.value,
        #             "msg": translation_loader.translation.t("model.parse_model_config_failed", ex=ex),
        #         }
        #     )
        #     return

    @staticmethod
    def parse_repo_id(url: str):
        if url.startswith("https://huggingface.co/") or url.startswith("https://www.huggingface.co/"):
            repo_id = "/".join(url.split("/")[3:5])
            return repo_id
        if url.count("/") == 1:
            return url
        return

    @staticmethod
    def extract_model_size(model_name) -> str:
        match = re.search(r"(\d+(\.\d+|x\d+)?[b|B])", model_name)
        if match:
            return match.group(0).replace("B", "b")
        return "latest"


api_router.add("/api/model/parse_model_url", ParseModelUrlHandler)
