from typing import Any, Optional


def resolve_parameters(
    parameter_rules: list[dict[str, Any]], override_params: Optional[dict[str, Any]]
) -> dict[str, Any]:
    override_params = override_params or {}
    resolved: dict[str, Any] = {}

    for rule in parameter_rules:
        model_param = rule["name"]
        input_param = rule.get("use_template", model_param)
        required = rule.get("required", False)
        default = rule.get("default")
        value = override_params.get(input_param, default)

        if isinstance(value, (int, float)):
            min_v = rule.get("min")
            max_v = rule.get("max")
            if min_v is not None and value < min_v:
                raise ValueError(f"Parameter '{input_param}' must be >= {min_v}")
            if max_v is not None and value > max_v:
                raise ValueError(f"Parameter '{input_param}' must be <= {max_v}")

        if required and value is None:
            raise ValueError(f"Missing required parameter '{input_param}'")

        if value is not None:
            resolved[model_param] = value

    return resolved
