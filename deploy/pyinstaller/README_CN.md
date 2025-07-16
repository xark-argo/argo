# 📦 Argo 后端 PyInstaller 打包指南

本目录用于将整个后端服务打包为可独立运行的单一可执行程序，方便本地部署、离线运行、封装桌面端等使用场景。

---

## 📁 目录结构说明

```
deploy/
    └── pyinstaller/
        ├── argo.spec              # 主 PyInstaller 打包入口文件
        └── hooks/                 # 自定义 hook 目录（解决动态导入问题）
            └── hooks.py
```

---

## ✅ 打包前准备

### 1. 安装 PyInstaller

使用 Poetry 安装（推荐）：

```bash
poetry add --dev pyinstaller
```

或者使用系统 pip：

```bash
pip install pyinstaller
```

### 2. 环境准备

在进行打包之前，请确保以下条件已满足，以保证程序在未打包状态下可正常运行：

- ✅ 后端入口为 `backend/main.py`，并能成功启动服务  
- ✅ 后端依赖安装完成：

  ```bash
  make install
  ```

- ✅ 若项目包含前端代码，确保前端已构建（如 Vue、React 应用）：

  ```bash
  make build-web
  ```

- ✅ 本地运行未打包程序无误（验证是否能正常响应请求）：

  ```bash
  make run
  ```

> 💡 如果在 `make run` 阶段程序无法正常启动或前端构建失败，建议先排查问题再执行打包，以避免生成异常的可执行文件。

---

## 🚀 快速构建方式（Make 命令）

推荐通过 `make build-exe` 命令一键打包：

```bash
# 如果在项目根目录
make build-exe
```

该命令等价于执行：

```bash
cd backend && poetry run pyinstaller ../deploy/pyinstaller/argo_build.spec \
		--distpath ../build/output \
		--workpath ../build
```

---

## 🧹 清理构建文件

使用：

```bash
make cleanup clean
```

会删除：

- `build/`
- `__pycache__/`

---

## 🧩 资源打包说明

你可以在 `utils.py` 中使用 `get_data_files()` 指定要包含在可执行程序中的资源路径：

```python
def get_data_files():
    return [
        ("resources", "backend/build/pyinstaller/resources"),
        ("configs", "backend/configs"),
        ("templates", "backend/templates"),
    ]
```

这些资源会在运行时被 PyInstaller 提取到临时目录，通过如下方式访问：

```python
from sys import _MEIPASS
import os

resource_path = os.path.join(getattr(sys, "_MEIPASS", "."), "resources", "node", "bin", "node")
```

---

## 🛠️ hook 文件说明（`hooks/`）

`deploy/pyinstaller/hooks/` 目录用于存放 PyInstaller 打包所需的 **运行时 hook** 和 **模块导入 hook** 脚本，确保程序在打包后仍能正常运行和加载依赖。

---

### ✅ 1. 运行时环境变量注入（`runtime_env_hook.py`）

由于 PyInstaller 打包后无法直接读取 `.env` 配置，推荐通过运行时 hook 设置必要的环境变量。

文件路径：`deploy/pyinstaller/hooks/runtime_env_hook.py`

```python
import os
import sys

# 控制功能开启
os.environ["ENABLE_MULTI_USER"] = "false"
os.environ["USE_ARGO_OLLAMA"] = "true"
os.environ["USE_ARGO_TRACKING"] = "true"
os.environ["USE_REMOTE_MODELS"] = "true"

# 资源路径绑定到 _MEIPASS
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(sys._MEIPASS, "resources", "huggingface", "hub")
os.environ["TIKTOKEN_CACHE_DIR"] = os.path.join(sys._MEIPASS, "resources", "tiktoken_cache")
os.environ["LLAMA_CPP_LIB_PATH"] = os.path.join(sys._MEIPASS, "llama_cpp", "lib")

# 防止本地请求走代理
os.environ["NO_PROXY"] = "http://127.0.0.1,localhost"
```

#### ✅ 在 `.spec` 中启用：

在 `Analysis(...)` 配置中添加：

```python
runtime_hooks=[
    os.path.join(spec_dir, 'hooks', 'runtime_env_hook.py'),
]
```

---

## ✅ 运行打包结果

进入构建目录：

```bash
cd build/output/argo-darwin_arm64
./argo  # Linux/macOS

# Windows 示例
argo.exe
```

---

## 🧪 调试建议

- 使用 `--clean` 避免缓存影响
- 使用 `--log-level=DEBUG` 观察打包详细日志
- 检查 `_MEIPASS` 路径，确保资源正确复制
- 如果 `import` 报错，尝试为该模块添加 hook 脚本

---

## 📌 常见问题

| 问题描述 | 可能原因 | 解决方案 |
|----------|-----------|----------|
| ❌ 启动后提示 `ModuleNotFoundError` | PyInstaller 未能打包动态依赖模块 | 添加 hook 文件：使用 `collect_submodules` 明确指定 `hiddenimports` |
| ❌ 运行时报错找不到资源文件（如 provider.yaml、前端 dist） | 未正确设置 `datas` 或资源未复制 | 确保 `.spec` 中通过 `datas = get_data_files()` 正确收集资源，或检查 `resources/` 是否打包进去了 |
| ❌ Node.js 无法执行 | 权限不足，未设置执行权限 | 在 `utils.prepare_node()` 中使用 `os.chmod(path, 0o775)` 设置为可执行 |
| ❌ 启动后 `.env` 未生效               | PyInstaller 打包后 `.env` 文件路径变更，默认在 `ARGO_STORAGE_PATH` 指定路径下（未设置时为用户主目录下的 `.argo/.env`） | 需要确保程序运行时正确读取 `ARGO_STORAGE_PATH` 下的 `.env` 文件，或者在启动脚本中显式加载该文件，避免因路径变化导致未生效 |
| ❌ llama.cpp 报错找不到动态库 | 没有设置 `LLAMA_CPP_LIB_PATH` 环境变量 | 在 hook 中设置 `os.environ["LLAMA_CPP_LIB_PATH"] = ...` 并确保 lib 路径存在 |
| ❌ 打包过慢或失败 | 构建缓存未清理 | 使用 `make cleanup` 清理缓存文件后重新打包 |
| ❌ HuggingFace 模型无法加载 | 缓存目录未映射或缺失 | 设置 `HUGGINGFACE_HUB_CACHE` 到 `_MEIPASS/resources/huggingface/hub` 并将相关模型预存进去 |
| ❌ 找不到 `deploy.pyinstaller.utils` | 相对导入错误或目录结构问题 | 确保 `.spec` 中路径设置正确，或将 `PYTHONPATH` 添加为 `backend` 父级 |

---