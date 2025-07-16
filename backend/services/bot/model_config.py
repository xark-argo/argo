import re

from core.entities.application_entities import PlanningStrategy
from database import db
from models.bot import Bot, BotModelConfig, get_bot

SUPPORT_TOOLS = [
    "dataset",
    "google_search",
    "web_reader",
    "wikipedia",
    "current_datetime",
    "mcp_tool",
]


class ModelConfigService:
    @staticmethod
    def update_model_config(bot_id: str, model_config: dict) -> tuple[BotModelConfig, str]:
        model_config = ModelConfigService.validate_configuration(config=model_config, bot_mode="agent-chat")

        warning_msg = ""
        num_ctx = model_config.get("model", {}).get("completion_params", {}).get("num_ctx", 2048)
        if num_ctx > 8192:
            warning_msg = "Size of context window is too large, it may cause out of memory"

        bot = get_bot(bot_id)
        if bot is None:
            raise ValueError(f"Bot with id {bot_id} does not exist")

        new_bot_model_config = BotModelConfig(
            bot_id=bot.id,
        )
        new_bot_model_config = new_bot_model_config.from_model_config_dict(model_config)

        with db.session_scope() as session:
            session.add(new_bot_model_config)
            session.flush()

            session.query(Bot).filter_by(id=bot_id).update({Bot.bot_model_config_id: new_bot_model_config.id})
            session.commit()

        return new_bot_model_config, warning_msg

    @classmethod
    def validate_configuration(cls, config: dict, bot_mode: str) -> dict:
        # model
        if "model" not in config:
            raise ValueError("model is required")

        if not isinstance(config["model"], dict):
            raise ValueError("model must be of object type")

        # model.name
        if "name" not in config["model"]:
            raise ValueError("model.name is required")

        # model.completion_params
        if "completion_params" not in config["model"]:
            raise ValueError("model.completion_params is required")

        config["model"]["completion_params"] = cls.validate_model_completion_params(
            config["model"]["completion_params"], config["model"]["name"]
        )

        # user_input_form
        if "user_input_form" not in config or not config["user_input_form"]:
            config["user_input_form"] = []

        if not isinstance(config["user_input_form"], list):
            raise ValueError("user_input_form must be a list of objects")

        variables: list[str] = []
        for item in config["user_input_form"]:
            key = list(item.keys())[0]

            if key == "text_input":
                item["text-input"] = item.pop("text_input")
                key = "text-input"

            if key not in ["text-input", "select", "paragraph", "number"]:
                raise ValueError(
                    "Keys in user_input_form list can only be 'text-input', 'paragraph', 'number' or 'select'"
                )

            form_item = item[key]
            if "label" not in form_item:
                raise ValueError("label is required in user_input_form")

            if not isinstance(form_item["label"], str):
                raise ValueError("label in user_input_form must be of string type")

            if "variable" not in form_item:
                raise ValueError("variable is required in user_input_form")

            if not isinstance(form_item["variable"], str):
                raise ValueError("variable in user_input_form must be of string type")

            pattern = re.compile(r"^(?!\d)[\u4e00-\u9fa5A-Za-z0-9_\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]{1,100}$")
            if pattern.match(form_item["variable"]) is None:
                raise ValueError("variable in user_input_form must be a string, and cannot start with a number")

            if form_item["variable"] in variables:
                raise ValueError(f'The variable name "{form_item["variable"]}" already exists')

            variables.append(form_item["variable"])

            if "required" not in form_item or not form_item["required"]:
                form_item["required"] = False

            if not isinstance(form_item["required"], bool):
                raise ValueError("required in user_input_form must be of boolean type")

            if key == "select":
                if "options" not in form_item or not form_item["options"]:
                    form_item["options"] = []

                if not isinstance(form_item["options"], list):
                    raise ValueError("options in user_input_form must be a list of strings")

                if "default" in form_item and form_item["default"] and form_item["default"] not in form_item["options"]:
                    raise ValueError("default value in user_input_form must be in the options list")

        # pre_prompt
        if "pre_prompt" not in config or not config["pre_prompt"]:
            config["pre_prompt"] = ""

        if not isinstance(config["pre_prompt"], str):
            raise ValueError("pre_prompt must be of string type")

        # prologue
        if "prologue" not in config or not config["prologue"]:
            config["prologue"] = ""

        if not isinstance(config["prologue"], str):
            raise ValueError("prologue must be of string type")

        # advanced_prompt
        if "advanced_prompt" not in config or not config["advanced_prompt"]:
            config["advanced_prompt"] = ""

        if not isinstance(config["advanced_prompt"], str):
            raise ValueError("advanced_prompt must be of string type")

        if "network" not in config or not config["network"]:
            config["network"] = False

        if "tool_config" not in config or not config["tool_config"]:
            config["tool_config"] = []

        if "plugin_config" not in config or not config["plugin_config"]:
            config["plugin_config"] = {}

        # agent_mode
        if "agent_mode" not in config or not config["agent_mode"]:
            config["agent_mode"] = {"enabled": False, "tools": []}
        if not isinstance(config["agent_mode"], dict):
            raise ValueError("agent_mode must be of object type")

        if "enabled" not in config["agent_mode"] or not config["agent_mode"]["enabled"]:
            config["agent_mode"]["enabled"] = False

        if not isinstance(config["agent_mode"]["enabled"], bool):
            raise ValueError("enabled in agent_mode must be of boolean type")

        if "strategy" not in config["agent_mode"] or not config["agent_mode"]["strategy"]:
            config["agent_mode"]["strategy"] = PlanningStrategy.TOOL_CALL.value

        if config["agent_mode"]["strategy"] not in [
            member.value for member in list(PlanningStrategy.__members__.values())
        ]:
            raise ValueError("strategy in agent_mode must be in the specified strategy list")

        if "tools" not in config["agent_mode"] or not config["agent_mode"]["tools"]:
            config["agent_mode"]["tools"] = []

        if not isinstance(config["agent_mode"]["tools"], list):
            raise ValueError("tools in agent_mode must be a list of objects")

        for tool in config["agent_mode"]["tools"]:
            key = tool["type"]
            if key not in SUPPORT_TOOLS:
                raise ValueError("Tool type in agent_mode.tools must be in the specified tool list")

            if "enabled" not in tool or not tool["enabled"]:
                tool["enabled"] = False

            if not isinstance(tool["enabled"], bool):
                raise ValueError("enabled in agent_mode.tools must be of boolean type")

            if key == "dataset":
                if "id" not in tool:
                    raise ValueError("id is required in dataset")

        if not isinstance(config["silly_character"], dict):
            raise ValueError("silly_character must be a dict")

        # Filter out extra parameters
        filtered_config = {
            "model": {
                "provider": config["model"]["provider"],
                "name": config["model"]["name"],
                "model_id": config["model"].get("model_id", ""),
                "mode": config["model"]["mode"],
                "completion_params": config["model"]["completion_params"],
                "color": config["model"].get("color", ""),
                "icon_url": config["model"].get("icon_url", ""),
            },
            "user_input_form": config["user_input_form"],
            "pre_prompt": config["pre_prompt"],
            "advanced_prompt": config["advanced_prompt"],
            "prologue": config["prologue"],
            "agent_mode": config["agent_mode"],
            "prompt_type": config["prompt_type"],
            "network": config["network"],
            "tool_config": config["tool_config"],
            "plugin_config": config["plugin_config"],
            "silly_character": config["silly_character"],
        }

        return filtered_config

    @classmethod
    def validate_model_completion_params(cls, cp: dict, model_name: str) -> dict:
        if not isinstance(cp, dict):
            raise ValueError("model.completion_params must be of object type")

        # stop
        if "stop" not in cp:
            cp["stop"] = []
        elif not isinstance(cp["stop"], list):
            raise ValueError("stop in model.completion_params must be of list type")

        if len(cp["stop"]) > 4:
            raise ValueError("stop sequences must be less than 4")

        if "num_predict" in cp and cp["num_predict"] > 0:
            cp["max_tokens"] = cp["num_predict"]

        return cp
