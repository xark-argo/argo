# from langchain_community.document_loaders.helpers import detect_file_encodings
# origin_detect_file_encodings = detect_file_encodings
# def new_detect_file_encodings(*args, **kwargs):
#     if 'timeout' not in kwargs:
#         kwargs['timeout'] = 20
#     return origin_detect_file_encodings(*args, **kwargs)

# detect_file_encodings = new_detect_file_encodings

import concurrent.futures
import importlib
from functools import wraps
from pathlib import Path
from typing import List, NamedTuple, Optional, Union, cast

# 动态导入 detect_file_encodings 函数
module_name = "langchain_community.document_loaders.helpers"
func_name = "detect_file_encodings"
module = importlib.import_module(module_name)
func = getattr(module, func_name)


@wraps(func)
def new_detect_file_encodings(*args, **kwargs):
    if "timeout" not in kwargs:
        kwargs["timeout"] = 20  # set new timeout
    return func(*args, **kwargs)


# replace
setattr(module, func_name, new_detect_file_encodings)

# need replace before import langchain_community
