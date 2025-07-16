from __future__ import annotations

import ctypes
import os
import pathlib
from typing import TYPE_CHECKING, Callable, NewType, Optional, Union

from core.third_party.llama_cpp._ctypes_extensions import (
    ctypes_function_for_shared_library,
    load_shared_library,
)

if TYPE_CHECKING:
    from core.third_party.llama_cpp._ctypes_extensions import CtypesArray

# Specify the base name of the shared library to load
_lib_base_name = "llama"
_override_base_path = os.environ.get("LLAMA_CPP_LIB_PATH")
if _override_base_path is None:
    from llama_cpp import llama_types

    _base_path = pathlib.Path(os.path.abspath(os.path.dirname(llama_types.__file__))) / "lib"
else:
    _base_path = pathlib.Path(_override_base_path)
# Load the library
_lib = load_shared_library(_lib_base_name, _base_path)
ctypes_function = ctypes_function_for_shared_library(_lib)

# struct llama_vocab;
llama_vocab_p = NewType("llama_vocab_p", int)
llama_vocab_p_ctypes = ctypes.c_void_p

# struct llama_model;
llama_model_p = NewType("llama_model_p", int)
llama_model_p_ctypes = ctypes.c_void_p

# typedef int32_t llama_token;
llama_token = ctypes.c_int32


# struct llama_model_kv_override {
#     enum llama_model_kv_override_type tag;

#     char key[128];


#     union {
#         int64_t val_i64;
#         double  val_f64;
#         bool    val_bool;
#         char    val_str[128];
#     };
# };
class llama_model_kv_override_value(ctypes.Union):
    _fields_ = [
        ("val_i64", ctypes.c_int64),
        ("val_f64", ctypes.c_double),
        ("val_bool", ctypes.c_bool),
        ("val_str", ctypes.c_char * 128),
    ]

    if TYPE_CHECKING:
        val_i64: int
        val_f64: float
        val_bool: bool
        val_str: bytes


class llama_model_kv_override(ctypes.Structure):
    _fields_ = [
        ("tag", ctypes.c_int),
        ("key", ctypes.c_char * 128),
        ("value", llama_model_kv_override_value),
    ]

    if TYPE_CHECKING:
        tag: int
        key: bytes
        value: Union[int, float, bool, bytes]


llama_progress_callback = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_float, ctypes.c_void_p)

# struct llama_model_tensor_buft_override {
#     const char * pattern;
#     ggml_backend_buffer_type_t buft;
# };


# struct llama_model_params {
#     // NULL-terminated list of devices to use for offloading (if NULL, all available devices are used)
#     ggml_backend_dev_t * devices;

#     // NULL-terminated list of buffer types to use for tensors that match a pattern
#     const struct llama_model_tensor_buft_override * tensor_buft_overrides;

#     int32_t n_gpu_layers; // number of layers to store in VRAM
#     enum llama_split_mode split_mode; // how to split the model across multiple GPUs

#     // main_gpu interpretation depends on split_mode:
#     // LLAMA_SPLIT_MODE_NONE: the GPU that is used for the entire model
#     // LLAMA_SPLIT_MODE_ROW: the GPU that is used for small tensors and intermediate results
#     // LLAMA_SPLIT_MODE_LAYER: ignored
#     int32_t main_gpu;

#     // proportion of the model (layers or rows) to offload to each GPU, size: llama_max_devices()
#     const float * tensor_split;

#     // Called with a progress value between 0.0 and 1.0. Pass NULL to disable.
#     // If the provided progress_callback returns true, model loading continues.
#     // If it returns false, model loading is immediately aborted.
#     llama_progress_callback progress_callback;

#     // context pointer passed to the progress callback
#     void * progress_callback_user_data;

#     // override key-value pairs of the model meta data
#     const struct llama_model_kv_override * kv_overrides;


#     // Keep the booleans together to avoid misalignment during copy-by-value.
#     bool vocab_only;    // only load the vocabulary, no weights
#     bool use_mmap;      // use mmap if possible
#     bool use_mlock;     // force system to keep model in RAM
#     bool check_tensors; // validate model tensor data
# };
class llama_model_params(ctypes.Structure):
    """Parameters for llama_model

    Attributes:
        devices (ctypes.Array[ggml_backend_dev_t]): NULL-terminated list of devices to use for offloading (if NULL, all available devices are used)
        tensor_buft_overrides (ctypes.Array[llama_model_tensor_buft_override]): NULL-terminated list of buffer types to use for tensors that match a pattern
        n_gpu_layers (int): number of layers to store in VRAM
        split_mode (int): how to split the model across multiple GPUs
        main_gpu (int): the GPU that is used for the entire model. main_gpu interpretation depends on split_mode: LLAMA_SPLIT_NONE: the GPU that is used for the entire model LLAMA_SPLIT_ROW: the GPU that is used for small tensors and intermediate results LLAMA_SPLIT_LAYER: ignored
        tensor_split (ctypes.Array[ctypes.ctypes.c_float]): proportion of the model (layers or rows) to offload to each GPU, size: llama_max_devices()
        progress_callback (llama_progress_callback): called with a progress value between 0.0 and 1.0. Pass NULL to disable. If the provided progress_callback returns true, model loading continues. If it returns false, model loading is immediately aborted.
        progress_callback_user_data (ctypes.ctypes.c_void_p): context pointer passed to the progress callback
        kv_overrides (ctypes.Array[llama_model_kv_override]): override key-value pairs of the model meta data
        vocab_only (bool): only load the vocabulary, no weights
        use_mmap (bool): use mmap if possible
        use_mlock (bool): force system to keep model in RAM
        check_tensors (bool): validate model tensor data"""

    if TYPE_CHECKING:
        devices: CtypesArray[ctypes.c_void_p]  # NOTE: unused
        tensor_buft_overrides: CtypesArray[llama_model_tensor_buft_override]  # NOTE: unused
        n_gpu_layers: int
        split_mode: int
        main_gpu: int
        tensor_split: CtypesArray[ctypes.c_float]
        progress_callback: Callable[[float, ctypes.c_void_p], bool]
        progress_callback_user_data: ctypes.c_void_p
        kv_overrides: CtypesArray[llama_model_kv_override]
        vocab_only: bool
        use_mmap: bool
        use_mlock: bool
        check_tensors: bool

    _fields_ = [
        ("devices", ctypes.c_void_p),  # NOTE: unnused
        ("tensor_buft_overrides", ctypes.c_void_p),  # NOTE: unused
        ("n_gpu_layers", ctypes.c_int32),
        ("split_mode", ctypes.c_int),
        ("main_gpu", ctypes.c_int32),
        ("tensor_split", ctypes.POINTER(ctypes.c_float)),
        ("progress_callback", llama_progress_callback),
        ("progress_callback_user_data", ctypes.c_void_p),
        ("kv_overrides", ctypes.POINTER(llama_model_kv_override)),
        ("vocab_only", ctypes.c_bool),
        ("use_mmap", ctypes.c_bool),
        ("use_mlock", ctypes.c_bool),
        ("check_tensors", ctypes.c_bool),
    ]


# // Initialize the llama + ggml backend
# // If numa is true, use NUMA optimizations
# // Call once at the start of the program
# LLAMA_API void llama_backend_init(bool numa);
# LLAMA_API void llama_backend_init(void);
@ctypes_function(
    "llama_backend_init",
    [],
    None,
)
def llama_backend_init():
    """Initialize the llama + ggml backend
    If numa is true, use NUMA optimizations
    Call once at the start of the program"""
    ...


# // Helpers for getting default parameters
# LLAMA_API struct llama_model_params          llama_model_default_params(void);
@ctypes_function(
    "llama_model_default_params",
    [],
    llama_model_params,
)
def llama_model_default_params() -> llama_model_params:
    """Get default parameters for llama_model"""
    ...


# DEPRECATED(LLAMA_API struct llama_model * llama_load_model_from_file(
#                          const char * path_model,
#           struct llama_model_params   params),
#         "use llama_model_load_from_file instead");
@ctypes_function(
    "llama_load_model_from_file",
    [ctypes.c_char_p, llama_model_params],
    llama_model_p_ctypes,
)
def llama_load_model_from_file(path_model: bytes, params: llama_model_params, /) -> Optional[llama_model_p]: ...


# LLAMA_API const struct llama_vocab * llama_model_get_vocab(const struct llama_model * model);
@ctypes_function("llama_model_get_vocab", [llama_model_p_ctypes], llama_vocab_p_ctypes)
def llama_model_get_vocab(model: llama_model_p, /) -> Optional[llama_vocab_p]: ...


# // Print system information
# LLAMA_API const char * llama_print_system_info(void);
@ctypes_function("llama_print_system_info", [], ctypes.c_char_p)
def llama_print_system_info() -> bytes: ...


# LLAMA_API void llama_free_model(struct llama_model * model);
@ctypes_function(
    "llama_free_model",
    [llama_model_p_ctypes],
    None,
)
def llama_free_model(model: llama_model_p, /): ...


# DEPRECATED(LLAMA_API llama_token llama_token_bos(const struct llama_vocab * vocab), "use llama_vocab_bos instead");
@ctypes_function(
    "llama_token_bos",
    [llama_vocab_p_ctypes],
    llama_token,
)
def llama_token_bos(vocab: llama_vocab_p, /) -> int: ...


# DEPRECATED(LLAMA_API llama_token llama_token_eos(const struct llama_vocab * vocab), "use llama_vocab_eos instead");
@ctypes_function(
    "llama_token_eos",
    [llama_vocab_p_ctypes],
    llama_token,
)
def llama_token_eos(vocab: llama_vocab_p, /) -> int: ...


# DEPRECATED(LLAMA_API const char * llama_token_get_text(const struct llama_vocab * vocab, llama_token token), "use llama_vocab_get_text instead");
@ctypes_function(
    "llama_token_get_text",
    [llama_vocab_p_ctypes, llama_token],
    ctypes.c_char_p,
)
def llama_token_get_text(vocab: llama_vocab_p, token: Union[llama_token, int], /) -> bytes: ...


# // Get the number of metadata key/value pairs
# LLAMA_API int32_t llama_model_meta_count(const struct llama_model * model);
@ctypes_function("llama_model_meta_count", [llama_model_p_ctypes], ctypes.c_int32)
def llama_model_meta_count(model: llama_model_p, /) -> int:
    """Get the number of metadata key/value pairs"""
    ...


# // Get metadata key name by index
# LLAMA_API int32_t llama_model_meta_key_by_index(const struct llama_model * model, int32_t i, char * buf, size_t buf_size);
@ctypes_function(
    "llama_model_meta_key_by_index",
    [
        llama_model_p_ctypes,
        ctypes.c_int32,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ],
    ctypes.c_int32,
)
def llama_model_meta_key_by_index(
    model: llama_model_p,
    i: Union[ctypes.c_int, int],
    buf: Union[bytes, CtypesArray[ctypes.c_char]],
    buf_size: int,
    /,
) -> int:
    """Get metadata key name by index"""
    ...


# // Get metadata value as a string by index
# LLAMA_API int32_t llama_model_meta_val_str_by_index(const struct llama_model * model, int32_t i, char * buf, size_t buf_size);
@ctypes_function(
    "llama_model_meta_val_str_by_index",
    [
        llama_model_p_ctypes,
        ctypes.c_int32,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ],
    ctypes.c_int32,
)
def llama_model_meta_val_str_by_index(
    model: llama_model_p,
    i: Union[ctypes.c_int, int],
    buf: Union[bytes, CtypesArray[ctypes.c_char]],
    buf_size: int,
    /,
) -> int:
    """Get metadata value as a string by index"""
    ...
