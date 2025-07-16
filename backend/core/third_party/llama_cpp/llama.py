import contextlib
import os
import sys

import core.third_party.llama_cpp._internals as internals
import core.third_party.llama_cpp._llama_cpp as llama_cpp
from core.third_party.llama_cpp._logger import set_verbose
from core.third_party.llama_cpp._utils import suppress_stdout_stderr


class Llama:
    """High-level Python wrapper for a llama.cpp model."""

    __backend_initialized = False

    def __init__(
        self,
        model_path: str,
        *,
        vocab_only: bool = False,
        verbose: bool = True,
    ):
        self.verbose = verbose
        self._stack = contextlib.ExitStack()

        set_verbose(verbose)

        if not Llama.__backend_initialized:
            with suppress_stdout_stderr(disable=verbose):
                llama_cpp.llama_backend_init()
            Llama.__backend_initialized = True

        self.model_path = model_path

        # Model Params
        self.model_params = llama_cpp.llama_model_default_params()
        self.model_params.vocab_only = vocab_only

        if not os.path.exists(model_path):
            raise ValueError(f"Model path does not exist: {model_path}")

        self._model = self._stack.enter_context(
            contextlib.closing(
                internals.LlamaModel(
                    path_model=self.model_path,
                    params=self.model_params,
                    verbose=self.verbose,
                )
            )
        )

        if self.verbose:
            print(llama_cpp.llama_print_system_info().decode("utf-8"), file=sys.stderr)

        try:
            self.metadata = self._model.metadata()
        except Exception as e:
            self.metadata = {}
            if self.verbose:
                print(f"Failed to load metadata: {e}", file=sys.stderr)

        if self.verbose:
            print(f"Model metadata: {self.metadata}", file=sys.stderr)

    def get_eos_token(self) -> str:
        eos_token_id = self._model.token_eos()
        eos_token = self._model.token_get_text(eos_token_id) if eos_token_id != -1 else ""
        return eos_token

    def get_bos_token(self) -> str:
        bos_token_id = self._model.token_bos()
        bos_token = self._model.token_get_text(bos_token_id) if bos_token_id != -1 else ""
        return bos_token

    def get_chat_template(self) -> str:
        if "tokenizer.chat_template" in self.metadata:
            return self.metadata["tokenizer.chat_template"]

        return ""


if __name__ == "__main__":
    model_file = "Qwen3-0.6B-Q8_0.gguf"
    llm = Llama(model_path=model_file, vocab_only=True, verbose=True)
    print("eos_token", llm.get_eos_token())
    print("bos_toekn", llm.get_bos_token())
    print("chat_template", llm.get_chat_template())
