import base64
import binascii
import json
import logging
import time
from datetime import datetime
from io import BytesIO
from typing import Optional, Union

from PIL import Image, PngImagePlugin

from models.bot import BotModelConfig, get_bot

SILLY_VARIABLE_MAP = {
    "model_mode": "Chat Mode",
    "character": "Character Name",
    "personality": "Character Personality",
    "description": "Character Description",
    "character_book": "Character World Book",
    "character_extensions": "Character Extensions",
    "scenario": "Scenario Setting",
    "mes_example": "Dialogue Example",
    "post_history_instructions": "Post-History Instructions",
    "user": "Username",
    "persona": "User Description",
    "persona_book": "User World Book",
}


def transform_input(input_data):
    transformed_data = []

    for item in input_data:
        for field_type, field_data in item.items():
            transformed_item = {
                "type": field_data["type"],
                "variable": field_data["variable"],
                "label": field_data["label"],
                "required": field_data.get("required", False),
                "default": field_data.get("default", ""),
            }

            if "options" in field_data:
                transformed_item["options"] = field_data["options"]

            transformed_data.append(transformed_item)

    return transformed_data


def reverse_transform_input(transformed_data):
    original_data = []

    for item in transformed_data:
        field_type = item["type"]

        field_data = {
            field_type: {
                "type": item["type"],
                "variable": item["variable"],
                "label": item["label"],
                "required": item.get("required", False),
                "default": item.get("default", ""),
            }
        }

        if "options" in item:
            field_data[field_type]["options"] = item["options"]

        original_data.append(field_data)

    return original_data


def preprocess_dict(character_info):
    if isinstance(character_info, dict):
        for key, value in character_info.items():
            if isinstance(value, str):
                value = value.replace("false", "False").replace("true", "True").replace("null", "None")
                try:
                    value = json.loads(value)
                    character_info[key] = preprocess_dict(value)
                except:
                    pass
                character_info[key] = value
            elif isinstance(value, (dict, list)):
                character_info[key] = preprocess_dict(value)
    elif isinstance(character_info, list):
        new_list = []
        for each in character_info:
            if isinstance(each, str):
                value = each.replace("false", "False").replace("true", "True").replace("null", "None")
                try:
                    value = json.loads(value)
                    new_list.append(preprocess_dict(value))
                except:
                    new_list.append(value)
            elif isinstance(each, (dict, list)):
                new_list.append(preprocess_dict(each))
            else:
                new_list.append(each)
        return new_list
    return character_info


def dump_dict(character_info: dict):
    for key, value in character_info.items():
        if key != "data" and isinstance(value, dict):
            character_info[key] = json.dumps(value, ensure_ascii=False, indent=2)
    data_info = character_info["data"]
    for key, value in data_info.items():
        if key in [
            "tags",
            "alternate_greetings",
            "extensions",
            "group_only_greetings",
            "character_book",
        ]:
            continue
        if isinstance(value, dict):
            data_info[key] = json.dumps(value, ensure_ascii=False, indent=2)
    character_book = data_info.get("character_book")
    entries = character_book.get("entries", [])
    new_entries = []
    for entry in entries:
        content = entry.get("content", "")
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        entry["content"] = content

        keys = entry.get("keys", [])
        new_keys = []
        for each_key in keys:
            if isinstance(each_key, str):
                new_keys.append(each_key.replace("True", "true").replace("False", "false").replace("None", "null"))
            elif isinstance(each_key, bool):
                new_keys.append(str(each_key).lower())
            elif each_key is None:
                new_keys.append("null")
        entry["keys"] = new_keys

        secondary_keys = entry.get("secondary_keys", [])
        new_keys = []
        for each_key in secondary_keys:
            if isinstance(each_key, str):
                new_keys.append(each_key.replace("True", "true").replace("False", "false").replace("None", "null"))
            elif isinstance(each_key, bool):
                new_keys.append(str(each_key).lower())
            elif each_key is None:
                new_keys.append("null")
        entry["secondary_keys"] = new_keys
        new_entries.append(entry)

    character_book["entries"] = new_entries
    data_info["character_book"] = character_book
    character_info["data"] = data_info
    return character_info


def load_silly_card(img_path: Union[str, BytesIO]):
    img = Image.open(img_path)
    img.getdata()
    meta_info = img.info
    if "chara" in meta_info:
        try:
            decoded_value = base64.b64decode(meta_info["chara"]).decode("utf-8")
            origin_character_info = json.loads(decoded_value)
            character_info = preprocess_dict(origin_character_info)
            return character_info
        except (binascii.Error, UnicodeDecodeError) as ex:
            logging.exception("An error occurred while decoding character info.")
            return {}
    return {}


def save_silly_card(
    character_info: dict,
    img_path: Union[str, BytesIO],
    output_file_path: Optional[str] = "",
    return_object: Optional[bool] = False,
):
    final_info = {}
    character_info = dump_dict(character_info)
    final_info["chara"] = base64.b64encode(json.dumps(character_info).encode("utf-8"))
    character_info["spec"] = "chara_card_v3"
    character_info["spec_version"] = "3.0"
    final_info["ccv3"] = base64.b64encode(json.dumps(character_info).encode("utf-8"))
    img = Image.open(img_path)
    pnginfo = PngImagePlugin.PngInfo()
    for key, value in final_info.items():
        pnginfo.add_text(key, value)
    if return_object:
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, "PNG", pnginfo=pnginfo)
        img_byte_arr.seek(0)
        return img_byte_arr
    elif output_file_path is not None:
        img.save(output_file_path, "PNG", pnginfo=pnginfo)


def import_user_input(character_info: dict, user_name: str, bot_name: str):
    user_input_form: list[dict[str, dict]] = []
    for key, value in SILLY_VARIABLE_MAP.items():
        if key in ["description", "personality", "scenario", "mes_example"]:
            real_value_outer = character_info.get(key, "")
            real_value_inner = character_info.get("data", {}).get(key, "")
            real_value = ""
            if real_value_outer:
                real_value = real_value_outer
            elif real_value_inner:
                real_value = real_value_inner
            if isinstance(real_value, dict):
                real_value = json.dumps(real_value, ensure_ascii=False, indent=2)
            user_input_form.append(
                {
                    "paragraph": {
                        "type": "paragraph",
                        "variable": key,
                        "label": value,
                        "default": real_value,
                    }
                }
            )
        elif key == "persona_book":
            user_input_form.append(
                {
                    "paragraph": {
                        "type": "paragraph",
                        "variable": key,
                        "label": value,
                        "default": "",
                    }
                }
            )
        elif key == "character_book":
            character_book = character_info.get("data", {}).get("character_book", {})
            entries = character_book.get("entries", [])
            new_entries = []
            for each in entries:
                content = each.get("content", "")
                if isinstance(content, dict):
                    each["content"] = json.dumps(content, ensure_ascii=False, indent=2)
                keys = each.get("keys", [])
                new_keys = []
                for each_key in keys:
                    if isinstance(each_key, str):
                        new_keys.append(
                            each_key.replace("True", "true").replace("False", "false").replace("None", "null")
                        )
                    elif isinstance(each_key, bool):
                        new_keys.append(str(each_key).lower())
                    elif each_key is None:
                        new_keys.append("null")
                each["keys"] = new_keys

                secondary_keys = each.get("secondary_keys", [])
                new_keys = []
                for each_key in secondary_keys:
                    if isinstance(each_key, str):
                        new_keys.append(
                            each_key.replace("True", "true").replace("False", "false").replace("None", "null")
                        )
                    elif isinstance(each_key, bool):
                        new_keys.append(str(each_key).lower())
                    elif each_key is None:
                        new_keys.append("null")
                each["secondary_keys"] = new_keys
                new_entries.append(each)
            character_book["entries"] = new_entries
            user_input_form.append(
                {
                    "paragraph": {
                        "type": "paragraph",
                        "variable": key,
                        "label": value,
                        "default": json.dumps(character_book, ensure_ascii=False, indent=2),
                    }
                }
            )
        elif key == "character":
            user_input_form.append(
                {
                    "text-input": {
                        "type": "text-input",
                        "variable": "char",
                        "label": value,
                        "default": bot_name,
                    }
                }
            )
        elif key == "user":
            user_input_form.append(
                {
                    "text-input": {
                        "type": "text-input",
                        "variable": key,
                        "label": value,
                        "default": user_name,
                    }
                }
            )
        elif key == "persona":
            user_input_form.append(
                {
                    "paragraph": {
                        "type": "paragraph",
                        "variable": key,
                        "label": value,
                        "default": "",
                    }
                }
            )
        elif key == "character_extensions":
            extension_info = character_info.get("data", {}).get("extensions", {})
            user_input_form.append(
                {
                    "paragraph": {
                        "type": "paragraph",
                        "variable": key,
                        "label": value,
                        "default": json.dumps(extension_info, ensure_ascii=False, indent=2),
                    }
                }
            )
        elif key == "model_mode":
            user_input_form.append(
                {
                    "select": {
                        "type": "select",
                        "variable": key,
                        "label": value,
                        "options": ["chat", "generate"],
                        "default": "chat",
                    }
                }
            )
        elif key == "post_history_instructions":
            post_history_info = character_info.get("data", {}).get("post_history_instructions", "")
            if isinstance(post_history_info, dict):
                post_history_info = json.dumps(post_history_info, ensure_ascii=False, indent=2)
            user_input_form.append(
                {
                    "paragraph": {
                        "type": "paragraph",
                        "variable": key,
                        "label": value,
                        "default": post_history_info,
                    }
                }
            )
    return user_input_form


def init_prompt() -> str:
    raw_prompt = """Write {{char}}'s next reply in a fictional chat between {{char}} and {{user}}."""
    return raw_prompt


def construct_silly_data(bot_model_config: BotModelConfig):
    bot_id = bot_model_config.bot_id
    bot = get_bot(bot_id)
    bot_name = bot.name

    raw_silly_config = bot_model_config.silly_character
    if raw_silly_config is None:
        return {}

    if bot_model_config.user_input_form is None:
        user_input_form_list = []
    else:
        user_input_form_list = json.loads(bot_model_config.user_input_form)

    user_input_form, other_input_form = {}, {}
    user_input_form_list = [value for item in user_input_form_list for value in item.values()]

    for each in user_input_form_list:
        key = each["variable"]
        user_input_form[key] = each
        if key not in SILLY_VARIABLE_MAP:
            other_input_form[key] = each

    raw_silly_config["name"] = bot_name
    raw_silly_config["data"]["name"] = bot_name

    default_description_str = user_input_form["description"].get("default", "")
    for key, value in other_input_form.items():
        default_description_str = default_description_str.replace(
            "{{" + key + "}}", "{{" + value.get("default", "") + "}}"
        )
    raw_silly_config["description"] = default_description_str
    raw_silly_config["data"]["description"] = default_description_str

    default_personality_str = user_input_form["personality"].get("default", "")
    for key, value in other_input_form.items():
        default_personality_str = default_personality_str.replace(
            "{{" + key + "}}", "{{" + value.get("default", "") + "}}"
        )
    raw_silly_config["personality"] = default_personality_str
    raw_silly_config["data"]["personality"] = default_personality_str

    default_scenario_str = user_input_form["scenario"].get("default", "")
    for key, value in other_input_form.items():
        default_scenario_str = default_scenario_str.replace("{{" + key + "}}", "{{" + value.get("default", "") + "}}")
    raw_silly_config["scenario"] = default_scenario_str
    raw_silly_config["data"]["scenario"] = default_scenario_str

    default_prologue_str = bot_model_config.prologue or ""
    alternate_greeting_list = raw_silly_config["data"].get("alternate_greetings", [])
    if not default_prologue_str:
        while alternate_greeting_list:
            item = alternate_greeting_list.pop()
            if item:
                default_prologue_str = item
                break
    for key, value in other_input_form.items():
        default_prologue_str = default_prologue_str.replace("{{" + key + "}}", "{{" + value.get("default", "") + "}}")
    raw_silly_config["first_mes"] = default_prologue_str
    raw_silly_config["data"]["first_mes"] = default_prologue_str
    raw_silly_config["data"]["alternate_greetings"] = alternate_greeting_list

    default_character_book_str = user_input_form["character_book"].get("default", "{}")
    if not default_character_book_str:
        default_character_book_str = "{}"
    for key, value in other_input_form.items():
        default_character_book_str = default_character_book_str.replace(
            "{{" + key + "}}", "{{" + value.get("default", "") + "}}"
        )
    raw_silly_config["data"]["character_book"] = json.loads(default_character_book_str)

    default_mes_example_str = user_input_form["mes_example"].get("default", "")
    for key, value in other_input_form.items():
        default_mes_example_str = default_mes_example_str.replace(
            "{{" + key + "}}", "{{" + value.get("default", "") + "}}"
        )
    raw_silly_config["mes_example"] = default_mes_example_str
    raw_silly_config["data"]["mes_example"] = default_mes_example_str

    now = datetime.now()
    milliseconds = int(round(time.time() * 1000)) % 1000
    time_str = now.strftime("%Y-%m-%d @%Hh%Mm%Ss")
    raw_silly_config["chat"] = f"{raw_silly_config['name']} - {time_str}"
    time_str = now.strftime(f"%Y-%m-%d @%Hh %Mm %Ss {milliseconds}ms")
    raw_silly_config["create_date"] = time_str
    return raw_silly_config
