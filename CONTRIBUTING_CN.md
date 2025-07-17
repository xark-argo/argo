# 🎉 感谢你对 Argo 的兴趣！

Argo 是一个模块化的 AI Agent 系统，整合了 LLM、多 Agent、MCP 工具协议、前后端协同机制等模块。我们欢迎所有形式的贡献，包括但不限于：

- Bug 修复
- 新功能开发
- 性能优化
- 文档补充
- 跨平台支持
- 部署方案改进

---

## 📁 项目结构总览

### 后端

Argo 的后端使用 Python 编写，使用 [Tornado](https://www.tornadoweb.org/en/stable/) 框架。它使用 [SQLAlchemy](https://www.sqlalchemy.org/) 作为 ORM。

<pre>
backend/
├── alembic/        # 数据库迁移脚本（Alembic）
├── configs/        # 配置项读取与初始化
├── core/           # Agent / LLM / MCP 等核心机制模块
├── dist/           # 前端构建产物（由 frontend 输出，供后端静态服务使用，可忽略）
├── docker/         # Docker 配置
├── events/         # 异步事件定义与处理
├── handlers/       # HTTP 接口控制器（Tornado Handler）
├── models/         # ORM 数据模型（SQLAlchemy 等）
├── resources/      # 静态资源
├── schemas/        # 请求参数定义与验证（Marshmallow Schema）
├── services/       # 核心业务逻辑实现（Service 层）
├── templates/      # swagger.json、HTML 页面等
├── tests/          # 单元测试
├── utils/          # 工具函数集合
└── main.py         # 应用入口
</pre>

---

### 前端

该网站使用基于 TypeScript 的 [Vite](https://vitejs.dev/) + [React](https://react.dev/) 模板进行构建。
<pre>
frontend/
├── public/               # 公共资源目录
├── src/                  # 源代码目录
│   ├── assets/           # 应用内使用的静态资源（如图片、SVG、音频等）
│   ├── components/       # 可复用组件库（如按钮、输入框、弹窗等）
│   ├── hooks/            # 自定义 React Hooks（如 useFetch、useTheme）
│   ├── layout/           # 页面布局组件（如 Header、Sidebar、Footer）
│   ├── lib/              # 封装的通用逻辑库/客户端（如请求库、第三方封装）
│   ├── pages/            # 页面组件（每个页面为一个独立模块）
│   ├── routes/           # 路由配置定义（如 react-router-dom 的 Route 定义）
│   ├── types/            # 全局 TypeScript 类型声明与接口定义
│   ├── utils/            # 工具函数集合（如日期、格式化、校验等）
│   ├── App.tsx           # React 应用的根组件
│   ├── App.css           # App 组件样式
│   ├── constants.tsx     # 应用中使用的常量集合
│   ├── index.css         # 全局样式文件
│   ├── main.tsx          # 应用入口文件，ReactDOM.createRoot 挂载点
│   ├── tailwind.css      # Tailwind CSS 的入口配置样式
│   └── vite-env.d.ts     # Vite 环境变量类型定义
└── index.html            # 应用 HTML 模板入口，Vite 注入构建资源的基础
</pre>

---

## 📌 在开始之前

请优先查看：

- [现有 Issue](https://github.com/xark-argo/argo/issues?q=is:issue)
- 如果是新增功能，请**先发起讨论或[创建 Issue](https://github.com/xark-argo/argo/issues/new/choose)**，确保方向一致后再开发
- 如果是修复 bug、小功能或文档更新，可以直接 PR

---

## 🚀 快速开始（开发者）

请参阅 [`docs/DEV_GUIDE_CN.md`](./docs/DEV_GUIDE_CN.md) 快速启动本地开发环境。

> ✅ 包含 `.env` 配置、前后端构建、依赖安装、运行服务等步骤。

---

## 🧑‍💻 贡献流程

### 1. Fork & Clone

```bash
git clone https://github.com/<your-name>/argo.git
cd argo
git remote add upstream https://github.com/xark-argo/argo.git
```

### 2. 创建特性分支

建议使用如下命名格式：

```bash
git checkout -b feat/agent-mem-optimization
```

命名格式推荐：

| 类型     | 示例                                      |
|----------|-------------------------------------------|
| 功能     | `feat/model-selector-ui`                  |
| 修复     | `fix/invalid-token-error`                 |
| 文档     | `docs/add-contributing-guide`             |
| 构建     | `build/pyinstaller-hook`                  |
| 重构     | `refactor/database-layer`                 |

---

## 📦 Commit 提交规范（推荐使用 Conventional Commits）

示例格式：

```bash
feat(agent): 支持多 Agent 状态隔离

fix(api): 修复接口未返回正确响应的问题

docs(readme): 增加本地启动指引
```

类型包括：

- `feat`: 新功能
- `fix`: 修复问题
- `docs`: 仅文档修改
- `style`: 格式/空格/缩进等（无语义改动）
- `refactor`: 重构（非 bug 修复或新功能）
- `test`: 增加/修改测试
- `build`: 构建相关（如 Docker、CI、PyInstaller）
- `chore`: 杂项（如依赖升级）

---

## ✅ 提交前检查项

请确保你已执行以下命令：

```bash
make format         # 格式化
make lint           # Mypy 类型检查 + Ruff 检查 + 测试
make build-web      # 如涉及前端变更
```

---

## 📄 PR 提交流程

1. 推送特性分支：

   ```bash
   git push origin feat/your-feature
   ```

2. 创建 Pull Request，并确保包含：

   - ✅ 清晰的标题和变更描述
   - ✅ 说明是否是破坏性改动（breaking change）
   - ✅ 是否涉及前端 UI 或模型兼容性
   - ✅ 如果有 UI，提供截图或功能演示

3. 等待 Maintainer 审核与讨论 ✅

---

## 🧪 单元测试说明

Argo 后端使用 `pytest + coverage`，测试路径在 `backend/tests/`。

运行测试：

```bash
make test
```

生成覆盖率报告：

```
assets/coverage/htmlcov/index.html
```

---

## 📦 如何添加新模型供应商支持？

请参考专门文档：

📄 [`core/model_providers/README_CN.md`](./backend/core/model_providers/README_CN.md)

---

## 📦 LangGraph DeepResearch 定制开发

请参考专门文档：

📄 [`core/agent/langgraph_agent/README_CN.md`](./backend/core/agent/langgraph_agent/README_CN.md)

---

## 🛠️ 如何使用 PyInstaller 打包？

请参考打包指南文档：

📄 [`deploy/pyinstaller/README_CN.md`](./deploy/pyinstaller/README_CN.md)

---

## 🎨 如何定制前端？

前端开发文档：

📄 [`frontend/README_CN.md`](https://github.com/xark-argo/argo-frontend/blob/main/README.md)

---

🌐 后端API 文档：

[http://localhost:11636/api/swagger/doc](http://localhost:11636/api/swagger/doc)

---

## 🧩 推荐工具

- 使用 [`pre-commit`](https://pre-commit.com/) 进行提交前格式化与检查：

  ```bash
  make pre-commit-install
  ```

- 配合 IDE 插件使用 Ruff + Mypy + Black

---

## 📄 许可证与行为准则

- 请阅读 [LICENSE](./LICENSE)
- 所有贡献者应遵守 [行为准则](./CODE_OF_CONDUCT.md)

---

## 💬 获取帮助

- 提交问题：[GitHub Issues](https://github.com/xark-argo/argo/issues/new)
- 快速讨论（如有）：加入我们的 Discord / 开发群
- 也欢迎对本指南提建议，直接修改 `CONTRIBUTING.md` 提交 PR 🙌

---

## ❤️ 感谢你的支持！

你的每一份贡献，都是推动 Argo 向前的动力！

欢迎你提交 PR、Issue、加入开发者交流群，一起打造更强大的 AI Agent 系统！

—— Argo 开发团队