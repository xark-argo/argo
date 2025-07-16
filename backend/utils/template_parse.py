# import json
# import logging
# import re
#
# import requests
# from jinja2 import Template
#
#
# def check_url(download_url) -> dict:
#     try:
#         res = requests.get(download_url).content.decode("utf-8")
#         template = json.loads(res)
#         if "chat_template" not in template:
#             logging.info("chat_template not found")
#             return {}
#         return template
#     except Exception:
#         logging.exception("Check url failed.")
#         return {}
#
#
# def generate_model_file(template: dict) -> str:
#     try:
#         data = {
#             "messages": [
#                 {"role": "system", "content": "OLLAMA_SYSTEM_TEMPLATE"},
#                 {"role": "user", "content": "OLLAMA_USER_TEMPLATE"},
#                 {"role": "assistant", "content": "OLLAMA_ASSISTANT_TEMPLATE"},
#             ],
#             "add_generation_prompt": False,
#         }
#         data.update(template)
#
#         template = Template(data["chat_template"])
#         model_file = template.render(data)
#         model_file = re.sub(r"{.*?}\s*", "", model_file)
#         logging.info(f"model render output: {model_file}")
#
#         reg = re.compile(r"\w+\s*OLLAMA_.*?_TEMPLATE", re.DOTALL)
#         res = reg.findall(model_file)
#         if len(res) == 0:
#             reg = re.compile(r"<[^>]*>\s*OLLAMA_.*?_TEMPLATE", re.DOTALL)
#             res = reg.findall(model_file)
#
#         reg = re.compile(r"<.+?>")
#         stop_flags = reg.findall(model_file)
#         stop_flags = list(set(stop_flags))
#
#         replace_list = []
#         for each in res:
#             if "OLLAMA_SYSTEM_TEMPLATE" in each:
#                 flag = each.replace("OLLAMA_SYSTEM_TEMPLATE", "").strip()
#                 flag_replace = f"{{{{ if .System }}}}{flag}"
#                 content = "{{ .System }}{{ end }}"
#                 temp = each.replace(flag, flag_replace).replace("OLLAMA_SYSTEM_TEMPLATE", content)
#                 replace_list.append(temp)
#             if "OLLAMA_USER_TEMPLATE" in each:
#                 flag = each.replace("OLLAMA_USER_TEMPLATE", "").strip()
#                 flag_replace = f"{{{{ if .Prompt }}}}{flag}"
#                 content = "{{ .Prompt }}{{ end }}"
#                 temp = each.replace(flag, flag_replace).replace("OLLAMA_USER_TEMPLATE", content)
#                 replace_list.append(temp)
#             if "OLLAMA_ASSISTANT_TEMPLATE" in each:
#                 temp = each.replace("OLLAMA_ASSISTANT_TEMPLATE", "{{ .Response }}")
#                 replace_list.append(temp)
#
#         for index, each in enumerate(res):
#             model_file = model_file.replace(each, replace_list[index])
#
#         if len(res) == 0:
#             model_file = model_file.replace("OLLAMA_SYSTEM_TEMPLATE", "{{ if .System }}{{ .System }}{{ end }}")
#             model_file = model_file.replace("OLLAMA_USER_TEMPLATE", "{{ if .User }}{{ .User }}{{ end }}")
#             model_file = model_file.replace(
#                 "OLLAMA_ASSISTANT_TEMPLATE",
#                 "{{ if .Assistant }}{{ .Assistant }}{{ end }}",
#             )
#
#         template_list = []
#         template_list.append(f'TEMPLATE "{model_file}"')
#
#         for stop_flag in stop_flags:
#             template_list.append(f"PARAMETER stop {stop_flag}")
#         return "\n".join(template_list)
#     except Exception:
#         logging.exception("Generate Model File failed.")
#         return ""
#
#
# if __name__ == "__main__":
#     # url = "https://huggingface.co/deepseek-ai/deepseek-coder-33b-instruct/resolve/main/tokenizer_config.json"
#     # url = "https://huggingface.co/ICTNLP/Llama-3.1-8B-Omni/resolve/main/tokenizer_config.json"
#     # url = "https://huggingface.co/Qwen/Qwen2.5-Coder-7B/resolve/main/tokenizer_config.json"
#     url = "https://huggingface.co/THUDM/glm-4-9b-chat/resolve/main/tokenizer_config.json"
#     template = check_url(url)
#     model_file = generate_model_file(template)
#     print(model_file)
