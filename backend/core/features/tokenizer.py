import logging
from threading import Lock
from typing import Any

from sentencepiece import SentencePieceProcessor
from tokenizers import Tokenizer

# Todo: simplify GPT2Tokenizer to delete transformers dependency, need to optimize later
# from transformers import GPT2Tokenizer
from core.entities.application_entities import ModelConfigEntity
from core.model_providers.manager import ModelMode
from utils.path import app_path

CHARS_PER_TOKEN = 3.35

TOKENIZER_PATHS = {
    **dict.fromkeys(["mistral", "mixtral"], app_path("resources/tokenizers/mistral.model")),
    **dict.fromkeys(["llama3", "llama-3"], app_path("resources/tokenizers/llama3.json")),
    "llama": app_path("resources/tokenizers/llama.model"),
    "claude": app_path("resources/tokenizers/claude.json"),
    "yi": app_path("resources/tokenizers/yi.model"),
    "qwen2": app_path("resources/tokenizers/qwen2.json"),
    "command-r": app_path("resources/tokenizers/command-r.json"),
    "jamba": app_path("resources/tokenizers/jamba.model"),
    **dict.fromkeys(["gemma", "gemini"], app_path("resources/tokenizers/gemma.model")),
    **dict.fromkeys(["nemo", "pixtral"], app_path("resources/tokenizers/nemo.json")),
    "deepseek": app_path("resources/tokenizers/deepseek.json"),
    "gpt2": app_path("resources/tokenizers/gpt2/"),
}

_lock = Lock()
_tokenizer_cache: dict[str, Any] = {}


def load_tokenizer(model_name):
    with _lock:
        match = next(
            ((key, path) for key, path in TOKENIZER_PATHS.items() if model_name.find(key) != -1),
            None,
        )
        if not match:
            return None

        key, path = match

        tokenizer = None
        if key in _tokenizer_cache:
            tokenizer = _tokenizer_cache[key]
        else:
            if path.endswith(".model"):
                tokenizer = SentencePieceProcessor()
                tokenizer.LoadFromFile(path)
            elif path.endswith(".json"):
                tokenizer = Tokenizer.from_file(path)
            else:
                # Todo: simplify GPT2Tokenizer to delete transformers dependency
                # tokenizer = GPT2Tokenizer.from_pretrained(path)
                pass

            _tokenizer_cache[key] = tokenizer

        if isinstance(tokenizer, Tokenizer):
            return lambda text: len(tokenizer.encode(text).tokens)
        if isinstance(tokenizer, SentencePieceProcessor):
            return lambda text: len(tokenizer.EncodeAsPieces(text))
        # Todo: simplify GPT2Tokenizer to delete transformers dependency
        # if isinstance(tokenizer, GPT2Tokenizer):
        #     return lambda text: len(tokenizer.encode(text))

        return None


def get_token_count(text, model_config: ModelConfigEntity):
    model_mode = model_config.mode
    model_name = model_config.model.lower()

    use_fallback_estimate = False
    if model_mode == ModelMode.GENERATE.value:
        fallback_model = "llama"
    else:
        fallback_model = "gpt2"
        use_fallback_estimate = True

    try:
        tokenizer_func = load_tokenizer(model_name) or load_tokenizer(fallback_model)
        if tokenizer_func:
            return tokenizer_func(str(text))
        else:
            # Todo: need to optimize
            return len(text)
    except Exception as e:
        logging.warning(f"An error occurred while counting tokens for {model_name}, {e}")
        pass

    if use_fallback_estimate:
        return len(text) + CHARS_PER_TOKEN - 1
    return 0
