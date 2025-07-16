import os
import sys

os.environ["ENABLE_MULTI_USER"] = "false"
os.environ["USE_ARGO_OLLAMA"] = "true"
os.environ["USE_ARGO_TRACKING"] = "true"
os.environ["DISABLE_LOCAL_OLLAMA_PRELOAD"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["USE_REMOTE_MODELS"] = "true"
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(sys._MEIPASS, "resources", "huggingface", "hub")
os.environ["TIKTOKEN_CACHE_DIR"] = os.path.join(sys._MEIPASS, "resources", "tiktoken_cache")
os.environ["LLAMA_CPP_LIB_PATH"] = os.path.join(sys._MEIPASS, "llama_cpp", "lib")
os.environ["NO_PROXY"] = "http://127.0.0.1,localhost"
