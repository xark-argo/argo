import ctypes
import os
from contextlib import ExitStack

import core.third_party.llama_cpp._llama_cpp as llama_cpp
from core.third_party.llama_cpp._utils import suppress_stdout_stderr

# Python wrappers over llama.h structs


class LlamaModel:
    """Intermediate Python wrapper for a llama.cpp llama_model.
    NOTE: For stability it's recommended you use the Llama class instead."""

    def __init__(
        self,
        *,
        path_model: str,
        params: llama_cpp.llama_model_params,
        verbose: bool = True,
    ):
        self.path_model = path_model
        self.params = params
        self.verbose = verbose
        self._exit_stack = ExitStack()

        model = None

        if not os.path.exists(path_model):
            raise ValueError(f"Model path does not exist: {path_model}")

        with suppress_stdout_stderr(disable=verbose):
            model = llama_cpp.llama_load_model_from_file(self.path_model.encode("utf-8"), self.params)

        if model is None:
            raise ValueError(f"Failed to load model from file: {path_model}")

        vocab = llama_cpp.llama_model_get_vocab(model)

        if vocab is None:
            raise ValueError(f"Failed to get vocab from model: {path_model}")

        self.model = model
        self.vocab = vocab

        def free_model():
            if self.model is None:
                return
            llama_cpp.llama_free_model(self.model)
            self.model = None

        self._exit_stack.callback(free_model)

    def close(self):
        self._exit_stack.close()

    def __del__(self):
        self.close()

    # Special tokens

    def token_bos(self) -> int:
        return llama_cpp.llama_token_bos(self.vocab)

    def token_eos(self) -> int:
        return llama_cpp.llama_token_eos(self.vocab)

    # Vocab

    def token_get_text(self, token: int) -> str:
        return llama_cpp.llama_token_get_text(self.vocab, token).decode("utf-8")

    # Extra
    def metadata(self) -> dict[str, str]:
        metadata: dict[str, str] = {}
        buffer_size = 1024
        buffer = ctypes.create_string_buffer(buffer_size)
        # zero the buffer
        buffer.value = b"\0" * buffer_size
        # iterate over model keys
        for i in range(llama_cpp.llama_model_meta_count(self.model)):
            nbytes = llama_cpp.llama_model_meta_key_by_index(self.model, i, buffer, buffer_size)
            if nbytes > buffer_size:
                buffer_size = nbytes + 1
                buffer = ctypes.create_string_buffer(buffer_size)
                nbytes = llama_cpp.llama_model_meta_key_by_index(self.model, i, buffer, buffer_size)
            key = buffer.value.decode("utf-8")
            nbytes = llama_cpp.llama_model_meta_val_str_by_index(self.model, i, buffer, buffer_size)
            if nbytes > buffer_size:
                buffer_size = nbytes + 1
                buffer = ctypes.create_string_buffer(buffer_size)
                nbytes = llama_cpp.llama_model_meta_val_str_by_index(self.model, i, buffer, buffer_size)
            value = buffer.value.decode("utf-8")
            metadata[key] = value
        return metadata

    @staticmethod
    def default_params():
        """Get the default llama_model_params."""
        return llama_cpp.llama_model_default_params()
