# import logging
from enum import IntEnum

# from pathlib import Path

# import torch
#
# from core.third_party.llama.convert_hf_to_gguf import Model, split_str_to_n_bytes

GGML_QUANT_VERSION = 2


class LlamaFileType(IntEnum):
    ALL_F32 = 0
    MOSTLY_F16 = 1  # except 1d tensors
    MOSTLY_Q4_0 = 2  # except 1d tensors
    MOSTLY_Q4_1 = 3  # except 1d tensors
    MOSTLY_Q4_1_SOME_F16 = 4  # tok_embeddings.weight and output.weight are F16
    # MOSTLY_Q4_2        = 5   # support has been removed
    # MOSTLY_Q4_3        = 6   # support has been removed
    MOSTLY_Q8_0 = 7  # except 1d tensors
    MOSTLY_Q5_0 = 8  # except 1d tensors
    MOSTLY_Q5_1 = 9  # except 1d tensors
    MOSTLY_Q2_K = 10  # except 1d tensors
    MOSTLY_Q3_K_S = 11  # except 1d tensors
    MOSTLY_Q3_K_M = 12  # except 1d tensors
    MOSTLY_Q3_K_L = 13  # except 1d tensors
    MOSTLY_Q4_K_S = 14  # except 1d tensors
    MOSTLY_Q4_K_M = 15  # except 1d tensors
    MOSTLY_Q5_K_S = 16  # except 1d tensors
    MOSTLY_Q5_K_M = 17  # except 1d tensors
    MOSTLY_Q6_K = 18  # except 1d tensors
    MOSTLY_IQ2_XXS = 19  # except 1d tensors
    MOSTLY_IQ2_XS = 20  # except 1d tensors
    MOSTLY_Q2_K_S = 21  # except 1d tensors
    MOSTLY_IQ3_XS = 22  # except 1d tensors
    MOSTLY_IQ3_XXS = 23  # except 1d tensors
    MOSTLY_IQ1_S = 24  # except 1d tensors
    MOSTLY_IQ4_NL = 25  # except 1d tensors
    MOSTLY_IQ3_S = 26  # except 1d tensors
    MOSTLY_IQ3_M = 27  # except 1d tensors
    MOSTLY_IQ2_S = 28  # except 1d tensors
    MOSTLY_IQ2_M = 29  # except 1d tensors
    MOSTLY_IQ4_XS = 30  # except 1d tensors
    MOSTLY_IQ1_M = 31  # except 1d tensors
    MOSTLY_BF16 = 32  # except 1d tensors

    GUESSED = 1024  # not specified in the model file


# def judge_model_architecture(architecture):
#     try:
#         Model.from_model_architecture(architecture)
#         return True
#     except NotImplementedError:
#         return False
#
#
# def convert(dir_model, out_type):
#     logging.info(f"start convert model: {dir_model}, type: {out_type}")
#
#     dir_model = Path(dir_model)
#     if not dir_model.is_dir():
#         raise RuntimeError(f"Error: {dir_model} is not a directory")
#
#     ftype_map: dict[str, LlamaFileType] = {
#         "f32": LlamaFileType.ALL_F32,
#         "f16": LlamaFileType.MOSTLY_F16,
#         "bf16": LlamaFileType.MOSTLY_BF16,
#         "q8_0": LlamaFileType.MOSTLY_Q8_0,
#         "auto": LlamaFileType.GUESSED,
#     }
#
#     fname_out = dir_model / f"ggml-model-{out_type}.gguf"
#
#     logging.info(f"Loading model: {dir_model.name}")
#
#     hparams = Model.load_hparams(dir_model)
#
#     with torch.inference_mode():
#         output_type = ftype_map[out_type]
#         model_architecture = hparams["architectures"][0]
#
#         try:
#             model_class = Model.from_model_architecture(model_architecture)
#         except NotImplementedError:
#             raise RuntimeError(f"Model {hparams['architectures'][0]} is not supported")
#
#         model_instance = model_class(
#             dir_model=dir_model,
#             ftype=output_type,
#             fname_out=fname_out,
#             is_big_endian=False,
#             use_temp_file=False,
#             eager=False,
#             metadata_override=None,
#             model_name=None,
#             split_max_tensors=0,
#             split_max_size=split_str_to_n_bytes("0"),
#             dry_run=False,
#             small_first_shard=False,
#         )
#
#         logging.info("Exporting model...")
#         model_instance.write()
#         out_path = model_instance.fname_out
#         logging.info(f"Model successfully exported to {out_path}")
