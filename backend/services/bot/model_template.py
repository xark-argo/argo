import json
from typing import Any

model_templates: dict[str, Any] = {
    # chat default mode
    "chat_default": {
        "bot": {"mode": "chat", "status": "normal"},
        "model_config": {
            "provider": "ollama",
            "model_id": "",
            "configs": {
                "prompt_template": "",
                "prompt_variables": [],
                "completion_params": {
                    "mirostat": 0,
                    "mirostat_eta": 0.1,
                    "mirostat_tau": 5.0,
                    "num_ctx": 4096,
                    "num_gpu": -1,
                    "num_predict": -1,
                    "repeat_last_n": 64,
                    "repeat_penalty": 1.1,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "tfs_z": 1,
                    "top_k": 40,
                    "frequency_penalty": 0,
                    "presence_penalty": 0,
                },
            },
            "model": json.dumps(
                {
                    "provider": "ollama",
                    "name": "",
                    "mode": "chat",
                    "completion_params": {
                        "mirostat": 0,
                        "mirostat_eta": 0.1,
                        "mirostat_tau": 5.0,
                        "num_ctx": 4096,
                        "num_gpu": -1,
                        "num_predict": -1,
                        "repeat_last_n": 64,
                        "repeat_penalty": 1.1,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "tfs_z": 1,
                        "top_k": 40,
                        "frequency_penalty": 0,
                        "presence_penalty": 0,
                    },
                }
            ),
            "network": False,
        },
    },
}

char_template = {
    "name": "default_character",
    "description": "",
    "personality": "",
    "scenario": "",
    "first_mes": "",
    "mes_example": "",
    "creatorcomment": "",
    "avatar": "none",
    "chat": "default_character - 2025-1-10 @15h 41m 09s 697ms",
    "talkativeness": "0.5",
    "fav": False,
    "tags": [],
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "default_character",
        "description": "",
        "personality": "",
        "scenario": "",
        "first_mes": "",
        "mes_example": "",
        "creator_notes": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "tags": [],
        "creator": "",
        "character_version": "",
        "alternate_greetings": [],
        "extensions": {
            "talkativeness": "0.5",
            "fav": False,
            "world": "",
            "depth_prompt": {"prompt": "", "depth": 4, "role": "system"},
        },
        "group_only_greetings": [],
    },
    "create_date": "2025-1-10 @15h 41m 09s 796ms",
}

char_model_templates: dict[str, Any] = {
    "chat_default": {
        "bot": {"mode": "chat", "status": "normal"},
        "model_config": {
            "provider": "ollama",
            "model_id": "",
            "configs": {
                "prompt_template": "",
                "prompt_variables": [],
                "completion_params": {
                    "mirostat": 0,
                    "mirostat_eta": 0.1,
                    "mirostat_tau": 5.0,
                    "num_ctx": 8192,
                    "num_gpu": -1,
                    "num_predict": 769,
                    "repeat_last_n": 0,
                    "repeat_penalty": 1.2,
                    "temperature": 0.7,
                    "top_p": 0.5,
                    "tfs_z": 1,
                    "top_k": 40,
                    "frequency_penalty": 1.0,
                    "presence_penalty": 1.1,
                },
            },
            "model": json.dumps(
                {
                    "provider": "ollama",
                    "name": "",
                    "mode": "chat",
                    "completion_params": {
                        "mirostat": 0,
                        "mirostat_eta": 0.1,
                        "mirostat_tau": 5.0,
                        "num_ctx": 8192,
                        "num_gpu": -1,
                        "num_predict": 769,
                        "repeat_last_n": 0,
                        "repeat_penalty": 1.2,
                        "temperature": 0.7,
                        "top_p": 0.5,
                        "tfs_z": 1,
                        "top_k": 40,
                        "frequency_penalty": 1.0,
                        "presence_penalty": 1.1,
                    },
                }
            ),
            "network": False,
        },
    },
}
