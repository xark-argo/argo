# 🎉 Thank You for Your Interest in Argo!

Argo is a modular AI Agent system that integrates components like LLM, multi-agent support, MCP tool protocol, and frontend-backend collaboration. We welcome all forms of contributions, including but not limited to:

- Bug fixes  
- New feature development  
- Performance optimization  
- Documentation improvements  
- Cross-platform support  
- Deployment enhancements  

---

## 📁 Project Structure Overview

### Backend

Argo's backend is written in Python using the [Tornado](https://www.tornadoweb.org/en/stable/) framework and uses [SQLAlchemy](https://www.sqlalchemy.org/) as the ORM.

<pre>
backend/
├── alembic/        # Database migration scripts (Alembic)
├── configs/        # Configuration loading and initialization
├── core/           # Core modules for Agent / LLM / MCP
├── dist/           # Frontend build artifacts (output from frontend, used for backend static serving, can be ignored)
├── docker/         # Docker configs
├── events/         # Async event definitions and handlers
├── handlers/       # HTTP controllers (Tornado Handlers)
├── models/         # ORM data models (SQLAlchemy, etc.)
├── resources/      # Static resources
├── schemas/        # Request schema definitions and validation (Marshmallow Schema)
├── services/       # Core business logic (Service layer)
├── templates/      # swagger.json, HTML templates, etc.
├── tests/          # Unit tests
├── utils/          # Utility functions
└── main.py         # Application entry point
</pre>

---

### Frontend

The frontend is built with [Vite](https://vitejs.dev/) + [React](https://react.dev/) based on TypeScript.

<pre>
frontend/
├── public/               # Public assets
├── src/                  # Source code
│   ├── assets/           # Static assets (images, SVGs, audio, etc.)
│   ├── components/       # Reusable UI components (buttons, inputs, modals, etc.)
│   ├── hooks/            # Custom React hooks (e.g. useFetch, useTheme)
│   ├── layout/           # Layout components (Header, Sidebar, Footer)
│   ├── lib/              # Shared libraries/clients (e.g. request library, 3rd-party wrappers)
│   ├── pages/            # Page components (each page is a module)
│   ├── routes/           # Route definitions (e.g. react-router-dom Route setup)
│   ├── types/            # Global TypeScript interfaces/types
│   ├── utils/            # Utility functions (date, formatting, validation, etc.)
│   ├── App.tsx           # Root React component
│   ├── App.css           # Styles for App component
│   ├── constants.tsx     # App-wide constants
│   ├── index.css         # Global styles
│   ├── main.tsx          # App entry point, ReactDOM.createRoot mount point
│   ├── tailwind.css      # Tailwind CSS entry configuration
│   └── vite-env.d.ts     # Vite environment variable type definitions
└── index.html            # HTML entry template for Vite to inject build artifacts
</pre>

---

## 📌 Before You Start

Please review:

- [Existing Issues](https://github.com/xark-argo/argo/issues?q=is:issue)
- For new features, please **start a discussion or [create an issue](https://github.com/xark-argo/argo/issues/new/choose)** to align direction before starting development
- For bug fixes, minor features, or documentation updates, you may open a PR directly

---

## 🚀 Quick Start (Developers)

Refer to [`docs/DEV_GUIDE_CN.md`](./docs/DEV_GUIDE.md) for setting up the local development environment.

> ✅ Covers `.env` setup, frontend/backend build, dependency installation, service startup, and more.

---

## 🧑‍💻 Contribution Workflow

### 1. Fork & Clone

```bash
git clone https://github.com/<your-name>/argo.git
cd argo
git remote add upstream https://github.com/xark-argo/argo.git
```

### 2. Create a Feature Branch

Suggested naming format:

```bash
git checkout -b feat/agent-mem-optimization
```

Recommended branch types:

| Type     | Example                                |
|----------|----------------------------------------|
| Feature  | `feat/model-selector-ui`              |
| Fix      | `fix/invalid-token-error`             |
| Docs     | `docs/add-contributing-guide`         |
| Build    | `build/pyinstaller-hook`              |
| Refactor | `refactor/database-layer`             |

---

## 📦 Commit Message Convention (Use Conventional Commits)

Example format:

```bash
feat(agent): support multi-agent state isolation

fix(api): fix incorrect API response

docs(readme): add local dev setup instructions
```

Common types:

- `feat`: new feature  
- `fix`: bug fix  
- `docs`: documentation only  
- `style`: formatting (no code logic changes)  
- `refactor`: code refactoring  
- `test`: add or update tests  
- `build`: build-related changes (Docker, CI, PyInstaller, etc.)  
- `chore`: miscellaneous changes (e.g., dependency upgrades)

---

## ✅ Pre-commit Checklist

Before submitting a PR, please ensure you’ve run:

```bash
make format         # Code formatting
make lint           # Mypy + Ruff + basic test checks
make build-web      # If frontend code is changed
```

---

## 📄 PR Submission Process

1. Push your feature branch:

   ```bash
   git push origin feat/your-feature
   ```

2. Create a Pull Request, and ensure it includes:

   - ✅ Clear title and description of changes
   - ✅ Whether it introduces breaking changes
   - ✅ Whether it affects UI or model compatibility
   - ✅ If it’s UI-related, provide screenshots or demo

3. Wait for Maintainers to review and discuss ✅

---

## 🧪 Unit Testing Guide

The backend uses `pytest + coverage`, with tests located in `backend/tests/`.

Run tests:

```bash
make test
```

Generate coverage report:

```
assets/coverage/htmlcov/index.html
```

---

## 📦 How to Add a New Model Provider?

See the dedicated guide:

📄 [`core/model_providers/README.md`](./backend/core/model_providers/README.md)

---

## 📦 LangGraph DeepResearch Custom Development

Please refer to the detailed documentation:

📄 [`core/agent/langgraph_agent/README.md`](./backend/core/agent/langgraph_agent/README.md)

---

## 🛠️ How to Package with PyInstaller?

Please refer to the packaging guide:

📄 [`deploy/pyinstaller/README.md`](./deploy/pyinstaller/README.md)

---

## 🎨 How to Customize the Frontend?

Frontend developer guide:

📄 [`frontend/README.md`](./frontend/README.md)

---

🌐 API Documentation (Backend):

[http://localhost:11636/api/swagger/doc](http://localhost:11636/api/swagger/doc)

---

## 🧩 Recommended Tools

- Use [`pre-commit`](https://pre-commit.com/) for pre-commit formatting and checks:

  ```bash
  make pre-commit-install
  ```

- Use Ruff + Mypy + Black with IDE integration

---

## 📄 License & Code of Conduct

- Please read [LICENSE](./LICENSE)
- All contributors should follow our [Code of Conduct](./CODE_OF_CONDUCT.md)

---

## 💬 Get Help

- Submit issues: [GitHub Issues](https://github.com/xark-argo/argo/issues/new)
- For quick discussions: Join our Discord / dev group
- Feedback on this guide? Feel free to update `CONTRIBUTING.md` via PR 🙌

---

## ❤️ Thank You for Your Support!

Every contribution helps push Argo forward.

You're welcome to submit PRs, Issues, or join the community to help build a more powerful AI Agent system together!

— The Argo Dev Team