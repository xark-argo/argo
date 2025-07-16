from typing import Any, Optional

DEFAULT_TEMPLATES = {
    "{{.Prompt}}",
    "{{ .Prompt }}",
    "",
}


def normalize_ollama_template(template: Optional[str]) -> Optional[str]:
    """
    Return `None` if the template is a known default or empty.
    Otherwise, return the cleaned template string.
    """
    if not template:
        return None

    stripped = template.strip()
    if stripped in DEFAULT_TEMPLATES:
        return None

    return stripped


def parse_parameters(parameters: Optional[str]) -> Optional[dict[str, Any]]:
    parameters = parameters or ""

    parameter_dict: dict[str, Any] = {}

    for line in parameters.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        parts = stripped.split(None, 1)
        if len(parts) == 2:
            key, value = parts

            if key in parameter_dict:
                if isinstance(parameter_dict[key], list):
                    parameter_dict[key].append(value)
                else:
                    parameter_dict[key] = [parameter_dict[key], value]
            else:
                parameter_dict[key] = value

    return parameter_dict or None


def build_ollama_modelfile(
    model: Optional[str] = None, ollama_template: Optional[str] = None, ollama_parameters: Optional[dict] = None
) -> str:
    """
    构造 Ollama Modelfile 内容，包含 TEMPLATE 和 PARAMETER。
    """

    modelfile_lines = []

    if model:
        modelfile_lines.append(f"FROM {model}")

    if ollama_template:
        modelfile_lines.append(f'TEMPLATE """{ollama_template}"""')

    parameters = ollama_parameters or {}

    for key, value in parameters.items():
        if not key:
            continue

        if isinstance(value, list):
            for item in value:
                if item:
                    modelfile_lines.append(f"PARAMETER {key} {item}")
        elif value:
            modelfile_lines.append(f"PARAMETER {key} {value}")

    return "\n".join(modelfile_lines)


def is_parameters_equal(model_params: Optional[dict], params: Optional[dict]) -> bool:
    model_params = model_params or {}
    params = params or {}

    def normalize(v):
        if isinstance(v, str):
            v = v.strip('"').strip()
            return v or None
        if isinstance(v, list):
            return {normalize(item) for item in v if normalize(item) is not None}
        return v

    model_norm = {k: normalize(v) for k, v in model_params.items() if normalize(v) is not None}
    params_norm = {k: normalize(v) for k, v in params.items() if normalize(v) is not None}

    for k, v in params_norm.items():
        if k not in model_norm:
            return False

        model_v = model_norm[k]

        if isinstance(v, set):
            if isinstance(model_v, set):
                if not v.issubset(model_v):
                    return False
            else:
                if model_v not in v:
                    return False
        else:
            if isinstance(model_v, set):
                if v not in model_v:
                    return False
            else:
                if v != model_v:
                    return False

    return True
