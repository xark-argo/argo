# 🛠️ Argo 本地开发启动指南

本文档帮助你快速在本地搭建 Argo 的完整开发环境（包含前后端）。

---

## ✅ 环境要求

请确保已安装：

| 工具        | 推荐版本                    |
|-------------|-------------------------|
| Python      | ≥ 3.11                  |
| Poetry      | ≥ 2.0.1                 |
| Node.js     | ≥ 18.x LTS              |
| Yarn / NPM  | ≥ Yarn 1.22.x 或 NPM 9.x |

---

## 🚀 快速启动步骤

### 1. 克隆项目

```bash
git clone https://github.com/xark-argo/argo.git
cd argo
```

## 🧱 3. 配置环境变量（.env）

Argo 后端依赖环境变量运行。请在 `backend/` 目录中创建 `.env` 文件：

```bash
cp backend/.env.example backend/.env
```

`.env.example` 中提供了常用的配置项，以下是关键说明：

| 变量名                  | 描述                                            |
|-------------------------|-----------------------------------------------|
| `ENABLE_MULTI_USER`     | 是否启用多用户模式（每个用户隔离 会话、机器人配置）                    |
| `OLLAMA_BASE_URL`       | 本地 Ollama 模型服务地址（默认端口 11434）                  |
| `USE_ARGO_OLLAMA`       | 是否启用本地 Ollama（如关闭则请求远程模型）                     |
| `USE_REMOTE_MODELS`     | 是否从远程模型服务中加载模型列表                              |
| `USE_ARGO_TRACKING`     | 启用匿名使用统计和错误上报（默认启用，无隐私数据）                     |
| `TOKENIZERS_PARALLELISM`| 控制 tokenizer 是否并行执行，避免某些模型出错                  |
| `NO_PROXY`              | 防止代理设置干扰本地 Ollama 请求（应设置为 `localhost,127.0.0.1`） |
| `ARGO_STORAGE_PATH`     | Argo 本地数据存储路径（可选，默认 `~/.argo`）                |

✅ 示例配置（来自 `.env.example`）：

```env
ENABLE_MULTI_USER=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
USE_ARGO_OLLAMA=true
USE_REMOTE_MODELS=false
USE_ARGO_TRACKING=true
TOKENIZERS_PARALLELISM=false
NO_PROXY=http://127.0.0.1,localhost
ARGO_STORAGE_PATH=
```

💡 你可以根据需要添加更多自定义变量（如私有模型地址、远程服务等）。

---

### 3. 安装后端依赖

```bash
make install
```

或等价于：

```bash
cd backend
poetry install
```

---

### 4. 构建前端（可选）

如果你需要使用 Web UI，请先初始化子模块（仅首次执行）：

```bash
git submodule update --init --recursive
```

然后执行前端构建：

```bash
make build-web
```

这将自动将前端构建好的 `dist/` 文件复制到后端目录。

---

### 5. 本地运行 Argo

```bash
make run [host=0.0.0.0] [port=11636]
```

你可以通过 host 和 port 参数自定义启动地址（可选）。如果未设置，则使用默认地址：：

```
http://localhost:11636
```

你可以访问：

- `http://localhost:11636/api/swagger/doc` 查看接口文档
- `http://localhost:11636/` 打开聊天 UI（如已构建前端）

---

## 🧪 可选开发命令

| 命令               | 描述                      |
|--------------------|-------------------------|
| `make run`         | 启动后端服务                  |
| `make install`     | 安装 Python 依赖（基于 Poetry） |
| `make build-web`   | 构建前端并复制到后端              |
| `make test`        | 执行测试（pytest + coverage） |
| `make lint`        | 全量格式检查、类型检查             |
| `make migration`   | 生成数据库迁移文件               |

---

## 🧩 常见问题排查

| 问题 | 解决方案                           |
|------|--------------------------------|
| 前端页面 404 | 是否执行了 `make build-web`？构建是否成功？ |
| `.env` 无效 | 需要确保`.env` 文件保存在backend目录下     |

---

## 📌 更多参考

- 💼 部署与打包参考：[deploy/pyinstaller/README_CN.md](../deploy/pyinstaller/README_CN.md)
- 🧑‍💻 参与贡献请参考：[CONTRIBUTING_CN.md](../CONTRIBUTING_CN.md)

---

如需更多帮助，欢迎通过 GitHub Issue 与我们联系！