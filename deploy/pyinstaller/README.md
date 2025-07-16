# 📦 Argo Backend PyInstaller Packaging Guide

This directory is used to package the entire backend service into a standalone executable, suitable for local deployment, offline use, desktop integration, etc.

---

## 📁 Directory Structure

```
deploy/
    └── pyinstaller/
        ├── argo.spec              # Main PyInstaller entry file
        └── hooks/                 # Custom hooks (to fix dynamic import issues)
            └── hooks.py
```

---

## ✅ Pre-Packaging Preparation

### 1. Install PyInstaller

Recommended installation via Poetry:

```bash
poetry add --dev pyinstaller
```

Or using system pip:

```bash
pip install pyinstaller
```

### 2. Environment Preparation

Before packaging, make sure the following are met to ensure the program runs correctly before packaging:

- ✅ Backend entry is `backend/main.py` and can start the service successfully  
- ✅ Backend dependencies are installed:

  ```bash
  make install
  ```

- ✅ If the project includes frontend code, ensure the frontend has been built (e.g., Vue, React app):

  ```bash
  make build-web
  ```

- ✅ The unbundled program runs correctly locally (verify it responds to requests):

  ```bash
  make run
  ```

> 💡 If `make run` fails or the frontend build doesn't succeed, fix issues before packaging to avoid producing a broken executable.

---

## 🚀 Quick Build with Make Command

It's recommended to use `make build-exe` for one-click packaging:

```bash
# From project root
make build-exe
```

Equivalent to manually executing:

```bash
cd backend && poetry run pyinstaller ../deploy/pyinstaller/argo_build.spec \
		--distpath ../build/output \
		--workpath ../build
```

---

## 🧹 Clean Build Files

Use:

```bash
make cleanup clean
```

This will delete:

- `build/`
- `__pycache__/`

---

## 🧩 Resource Packaging Guide

You can use `get_data_files()` in `utils.py` to include resources in the executable:

```python
def get_data_files():
    return [
        ("resources", "backend/build/pyinstaller/resources"),
        ("configs", "backend/configs"),
        ("templates", "backend/templates"),
    ]
```

These resources will be extracted by PyInstaller at runtime and accessed like this:

```python
from sys import _MEIPASS
import os

resource_path = os.path.join(getattr(sys, "_MEIPASS", "."), "resources", "node", "bin", "node")
```

---

## 🛠️ About Hook Files (`hooks/`)

The `deploy/pyinstaller/hooks/` directory contains runtime and import hook scripts needed for PyInstaller to ensure all dependencies load correctly after packaging.

---

### ✅ 1. Runtime Environment Variable Injection (`runtime_env_hook.py`)

Since PyInstaller can't read `.env` files after packaging, it's recommended to inject necessary env variables in a runtime hook.

File path: `deploy/pyinstaller/hooks/runtime_env_hook.py`

```python
import os
import sys

# Enable or disable features
os.environ["ENABLE_MULTI_USER"] = "false"
os.environ["USE_ARGO_OLLAMA"] = "true"
os.environ["USE_ARGO_TRACKING"] = "true"
os.environ["USE_REMOTE_MODELS"] = "true"

# Bind resources to _MEIPASS
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(sys._MEIPASS, "resources", "huggingface", "hub")
os.environ["TIKTOKEN_CACHE_DIR"] = os.path.join(sys._MEIPASS, "resources", "tiktoken_cache")
os.environ["LLAMA_CPP_LIB_PATH"] = os.path.join(sys._MEIPASS, "llama_cpp", "lib")

# Prevent proxy interference for localhost
os.environ["NO_PROXY"] = "http://127.0.0.1,localhost"
```

#### ✅ Enable in `.spec`:

In `Analysis(...)` config, add:

```python
runtime_hooks=[
    os.path.join(spec_dir, 'hooks', 'runtime_env_hook.py'),
]
```

---

## ✅ Run the Executable

Go to the build directory:

```bash
cd build/output/argo-darwin_arm64
./argo  # Linux/macOS

# On Windows
argo.exe
```

---

## 🧪 Debugging Tips

- Use `--clean` to avoid cache issues
- Use `--log-level=DEBUG` for detailed logs
- Check `_MEIPASS` path to ensure resources are copied correctly
- If `import` fails, consider adding a hook script for that module

---

## 📌 Common Issues

| Problem Description                              | Possible Cause                          | Solution                                                                 |
|--------------------------------------------------|------------------------------------------|--------------------------------------------------------------------------|
| ❌ `ModuleNotFoundError` after startup           | PyInstaller missed dynamically imported modules | Add a hook file using `collect_submodules` to specify `hiddenimports` |
| ❌ Missing resources (like provider.yaml, frontend dist) | `datas` not set or files not copied     | Ensure `.spec` uses `datas = get_data_files()` and resources are included |
| ❌ Node.js not executable                        | Permissions not set                     | Use `os.chmod(path, 0o775)` in `utils.prepare_node()`                    |
| ❌ `.env` not working                            | `.env` path changes after packaging     | Load from `ARGO_STORAGE_PATH` at runtime or load manually in startup     |
| ❌ llama.cpp library not found                   | Missing `LLAMA_CPP_LIB_PATH` env var    | Set it in hook script and ensure path exists                            |
| ❌ Slow or failed build                          | Unclean cache                           | Run `make cleanup` then retry                                             |
| ❌ HuggingFace models not loading                | Cache not mapped                        | Set `HUGGINGFACE_HUB_CACHE` to `_MEIPASS/resources/huggingface/hub`      |
