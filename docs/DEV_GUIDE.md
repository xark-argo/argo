# 🛠️ Argo Local Development Startup Guide

This document helps you quickly set up the complete Argo development environment locally (including both backend and frontend).

---

## ✅ Environment Requirements

Please ensure the following are installed:

| Tool        | Recommended Version           |
|-------------|------------------------------|
| Python      | ≥ 3.11                       |
| Poetry      | ≥ 2.0.1                      |
| Node.js     | ≥ 18.x LTS                   |
| Yarn / NPM  | ≥ Yarn 1.22.x or NPM 9.x     |

---

## 🚀 Quick Start Steps

### 1. Clone the Project

```bash
git clone https://github.com/xark-argo/argo.git
cd argo
```

## 🧱 3. Configure Environment Variables (.env)

The Argo backend relies on environment variables to run. Please create a `.env` file in the `backend/` directory:

```bash
cp backend/.env.example backend/.env
```

`.env.example` provides commonly used configuration options. Below are key explanations:

| Variable Name           | Description                                                                                |
|-------------------------|--------------------------------------------------------------------------------------------|
| `ENABLE_MULTI_USER`     | Whether to enable multi-user mode (each user has isolated sessions, bot config)            |
| `OLLAMA_BASE_URL`       | Local Ollama model service address (default port 11434)                                    |
| `USE_ARGO_OLLAMA`       | Whether to enable local Ollama (if disabled, requests remote models)                       |
| `USE_REMOTE_MODELS`     | Whether to load models from remote model service                                           |
| `USE_ARGO_TRACKING`     | Enable anonymous usage tracking and error reporting (enabled by default, no private data)  |
| `TOKENIZERS_PARALLELISM`| Controls whether tokenizer runs in parallel to avoid model errors                          |
| `NO_PROXY`              | Prevent proxy settings from affecting local Ollama requests (set to `localhost,127.0.0.1`) |
| `ARGO_STORAGE_PATH`     | Argo local data storage path (optional, default is `~/.argo`)                              |

✅ Example configuration (from `.env.example`):

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

💡 You can add more custom variables as needed (e.g., private model address, remote services, etc.).

---

### 3. Install Backend Dependencies

```bash
make install
```

Or equivalently:

```bash
cd backend
poetry install
```

---

### 4. Build Frontend (Optional)

If you need to use the Web UI, first initialize the submodules (only needed on first run):

```bash
git submodule update --init --recursive
```

Then build the frontend:
```bash
make build-web
```

This will automatically copy the built frontend `dist/` files to the backend directory.

---

### 5. Run Argo Locally

```bash
make run [host=0.0.0.0] [port=11636]
```

You can customize the startup address using the host and port parameters (optional). If not set, the default is:

```
http://localhost:11636
```

You can access:

- `http://localhost:11636/api/swagger/doc` to view API docs
- `http://localhost:11636/` to open the chat UI (if frontend is built)

---

## 🧪 Optional Development Commands

| Command           | Description                              |
|--------------------|------------------------------------------|
| `make run`         | Start backend service                    |
| `make install`     | Install Python dependencies (via Poetry) |
| `make build-web`   | Build frontend and copy to backend       |
| `make test`        | Run tests (pytest + coverage)            |
| `make lint`        | Full format and type check               |
| `make migration`   | Generate database migration files        |

---

## 🧩 Common Troubleshooting

| Issue            | Solution                                                  |
|------------------|-----------------------------------------------------------|
| Frontend 404     | Did you run `make build-web`? Was the build successful?   |
| `.env` not working | Ensure `.env` file is saved in the `backend` directory    |

---

## 📌 More References

- 💼 Deployment & packaging: [deploy/pyinstaller/README.md](../deploy/pyinstaller/README.md)
- 🧑‍💻 Contribution guide: [CONTRIBUTING.md](../CONTRIBUTING.md)

---

For further assistance, feel free to reach out via GitHub Issues!