import logging
import re
from typing import Any, Callable, Optional, TypeVar

from jinja2 import Template

from core.third_party.ollama_utils.chat_template_automap import (
    OLLAMA_CHAT_TEMPLATE_MAPPING,
    OllamaChatTemplateMapEntry,
)

RE_SPECIAL_TOKEN = r"<[|_A-Za-z0-9]+>|\[[A-Z]+\]|<\uFF5C[\u2581A-Za-z]+\uFF5C>"

T = TypeVar("T")


def deduplicate_array(arr: list[T]) -> list[T]:
    seen = set()
    result = []
    for item in arr:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


CUSTOM_TEMPLATE_MAPPING: list[Callable[[str], Optional[dict[str, Any]]]] = [
    lambda gguf_tmpl: (
        {"ollamaTmpl": "<用户>{{ .Prompt }}<AI>"}
        if re.search(r"<用户>", gguf_tmpl) and re.search(r"<AI>", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ .System }}\n### Instruction:\n{{ .Prompt }}\n### Response:\n",
            "stop": "### Instruction:",
        }
        if re.search(r"### Instruction:", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ .System }}\nHuman: {{ .Prompt }}\n\nAssistant:",
            "stop": "Human:",
        }
        if re.search(r"Human:", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "<start_of_turn>user\n{{ if .System }}{{ .System }} {{ end }}{{ .Prompt }}<end_of_turn>\n<start_of_turn>model\n{{ .Response }}<end_of_turn>\n",
            "stop": "<end_of_turn>",
        }
        if re.search(r"<start_of_turn>", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ if .System }}<s>system\n{{ .System }}</s>{{ end }}{{ if .Prompt }}<s>user\n{{ .Prompt }}</s>{{ end }}<s>assistant\n{{ .Response }}</s>",
            "stop": "</s>",
        }
        if re.search(r"(bos_token|'<s>') \+ message\['role'\]", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n{{ .System }}</s>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n{{ .Prompt }}</s>{{ end }}<|start_header_id|>assistant<|end_header_id|>\n\n{{ .Response }}</s>",
            "stop": "</s>",
        }
        if re.search(r"<\|start_header_id\|>", gguf_tmpl) and re.search(r"eos_token|<\/s>", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ if .System }}<|system|>\n{{ .System }}<|end|>\n{{ end }}{{ if .Prompt }}<|user|>\n{{ .Prompt }}<|end|>\n{{ end }}<|assistant|>\n{{ .Response }}<|end|>",
            "stop": "<|end|>",
        }
        if re.search(r"<\|assistant\|>", gguf_tmpl) and re.search(r"<\|end\|>", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ if .System }}<|system|>\n{{ .System }}{{ end }}{{ if .Prompt }}<|user|>\n{{ .Prompt }}{{ end }}<|assistant|>\n{{ .Response }}",
            "stop": "<|user|>",
        }
        if re.search(r"<\|{{ item\['role'\] }}\|>", gguf_tmpl) and re.search(r"<\|begin_of_image\|>", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": "{{ if .System }}<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>{{ .System }}<|END_OF_TURN_TOKEN|>{{ end }}{{ if .Prompt }}<|START_OF_TURN_TOKEN|><|USER_TOKEN|>{{ .Prompt }}<|END_OF_TURN_TOKEN|>{{ end }}<|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|><|START_RESPONSE|>{{ .Response }}<|END_RESPONSE|><|END_OF_TURN_TOKEN|>",
            "stop": "<|END_OF_TURN_TOKEN|>",
        }
        if re.search(r"<\|START_OF_TURN_TOKEN\|>", gguf_tmpl) and re.search(r"<\|USER_TOKEN\|>", gguf_tmpl)
        else None
    ),
    lambda gguf_tmpl: (
        {
            "ollamaTmpl": '{{- range $index, $_ := .Messages }}\n{{- if eq .Role "system" }}[SYSTEM_PROMPT]{{ .Content }}[/SYSTEM_PROMPT]\n{{- else if eq .Role "user" }}\n{{- if and (le (len (slice $.Messages $index)) 2) $.Tools }}[AVAILABLE_TOOLS]{{ $.Tools }}[/AVAILABLE_TOOLS]\n{{- end }}[INST]{{ .Content }}[/INST]\n{{- else if eq .Role "assistant" }}\n{{- if .Content }}{{ .Content }}\n{{- if not (eq (len (slice $.Messages $index)) 1) }}</s>\n{{- end }}\n{{- else if .ToolCalls }}[TOOL_CALLS][\n{{- range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}\n{{- end }}]</s>\n{{- end }}\n{{- else if eq .Role "tool" }}[TOOL_RESULTS]{"content": {{ .Content }}}[/TOOL_RESULTS]\n{{- end }}\n{{- end }}',
            "stop": "[INST]",
        }
        if re.search(r"Mistral Small 3", gguf_tmpl) and re.search(r"2023-10-01", gguf_tmpl)
        else None
    ),
]


def convert_gguf_template_to_ollama(
    gguf: dict[str, Any],
) -> Optional[OllamaChatTemplateMapEntry]:
    if not gguf or not gguf.get("chat_template"):
        return None

    chat_template = gguf["chat_template"]
    truncated_gguf_tmpl = chat_template[:128]

    for tmpl in OLLAMA_CHAT_TEMPLATE_MAPPING:
        if tmpl.gguf and tmpl.gguf[:128] == truncated_gguf_tmpl:
            return tmpl

    tok_gguf = set(re.findall(RE_SPECIAL_TOKEN, chat_template))
    if tok_gguf:
        for tmpl in OLLAMA_CHAT_TEMPLATE_MAPPING:
            value = tmpl.ollama.get("tokens", [])
            tok_ollama = set(value) if isinstance(value, list) else set()
            if tok_gguf == tok_ollama:
                return tmpl

    for custom_matching in CUSTOM_TEMPLATE_MAPPING:
        matched = custom_matching(chat_template)
        if matched:
            logging.info(f"🔍 Custom map Jinja to Go:\n\n```{matched['ollamaTmpl']}```")
            return OllamaChatTemplateMapEntry(
                model="custom-matching",
                gguf=chat_template,
                template=matched["ollamaTmpl"],
                params={"stop": matched.get("stop", [])},
            )

    converted = convert_jinja_to_go_template(gguf)
    if converted:
        stop = re.findall(RE_SPECIAL_TOKEN, converted["tmpl"])
        if "###" in chat_template:
            stop.append("###")
        elif converted.get("stop"):
            stop.append(converted["stop"])

        logging.info(f"🙏 Converted Jinja to Go:\n\n```{converted['tmpl']}```")
        return OllamaChatTemplateMapEntry(
            model="auto-conversion",
            template=converted["tmpl"],
            gguf=chat_template,
            params={"stop": deduplicate_array(stop)},
        )

    logging.error(f"❌ Cannot map jinja template:\n\n```{chat_template[:200]}...```")

    return None


def convert_jinja_to_go_template(gguf: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not gguf.get("chat_template"):
        return None

    try:
        jinja = Template(gguf["chat_template"])

        system_msg = {"role": "system", "content": "{{ .System }}"}
        user_msg = {"role": "user", "content": "{{ .Prompt }}"}
        assistant_msg = {"role": "assistant", "content": "{{ .Response }}"}

        def format_msgs(msgs: list[dict[str, str]], retried: bool = False) -> str:
            try:
                return jinja.render(
                    {
                        "messages": msgs,
                        "bos_token": gguf.get("bos_token", ""),
                        "eos_token": gguf.get("eos_token", ""),
                        "add_generation_prompt": False,
                    }
                )
            except Exception:
                if retried:
                    return ""
                filtered_msgs = [m for m in msgs if m["role"] != "system"]
                return format_msgs(filtered_msgs, retried=True)

        def added_part(a: str, b: str) -> str:
            return b[len(a) :]

        # System role
        formatted_system = format_msgs([system_msg])

        # Assistant role
        formatted_resp0 = format_msgs([system_msg, user_msg])
        formatted_resp1 = format_msgs([system_msg, user_msg, assistant_msg])
        formatted_resp = added_part(formatted_resp0, formatted_resp1)

        # User role
        formatted_user0 = formatted_resp1
        formatted_user1 = format_msgs([system_msg, user_msg, assistant_msg, user_msg])
        formatted_user = added_part(formatted_user0, formatted_user1)

        # 判断是否需要特殊处理 system
        if re.search(r"{{\s*\.System\s*}}", formatted_system):
            go_tmpl = (
                f"{{{{ if .System }}}}{formatted_system}{{{{ end }}}}"
                f"{{{{ if .Prompt }}}}{formatted_user}{{{{ end }}}}{formatted_resp}"
            )
        else:
            formatted_user_content = formatted_user.replace("{{ .Prompt }}", "{{ .Content }}")
            formatted_resp_content = formatted_resp.replace("{{ .Response }}", "{{ .Content }}")
            added_assistant_prompt = formatted_resp.split("{{ .Response }}")[0]
            go_tmpl = (
                f"{formatted_system}{{{{- range .Messages }}}}"
                f'{{{{- if eq .Role "user" }}}}{formatted_user_content}'
                f'{{{{- else if eq .Role "assistant" }}}}{formatted_resp_content}'
                f"{{{{- end }}}}{{{{- end }}}}{added_assistant_prompt}"
            )

        # 提取 stop sequence
        stop_sequence_match = re.split(r"{{\s*\.Prompt\s*}}.*", formatted_user, flags=re.DOTALL)[0].strip()
        stop_sequence = stop_sequence_match if len(stop_sequence_match) >= 2 else None

        return {
            "tmpl": go_tmpl,
            "stop": stop_sequence,
        }
    except Exception:
        return None
