# 🧠 LangGraph Agent 开发手册

LangGraph Agent 是一个模块化、多节点、状态驱动的 Agent 编排系统，结合了 LangGraph、LangChain、LLM、MCP 工具协议，实现了规划、执行、报告的自动化 Agent 工作流。

---

## 📁 项目结构概览

```
core/agent/langgraph_agent/
├── builder.py                # 构建 LangGraph 工作流图
├── nodes.py                  # 所有 Agent 节点定义
├── prompts/
│   ├── configuration.py      # Configuration 配置模型
│   ├── planner_model.py      # Plan / Step 数据结构
│   ├── report_style.py       # 报告风格枚举
│   └── template.py           # Jinja2 模板渲染工具
├── tools/                    # Agent 工具，如 Python REPL
├── types.py                  # Agent 状态定义
├── utils/                    # 辅助工具，如 JSON 修复
```

---

## ⚙️ 核心组件说明

### 1. `State` 状态模型

`State` 继承自 `MessagesState`，是 LangGraph Agent 运行时的核心上下文状态，保存智能体当前的对话信息、计划、资源和控制标志。

路径：`types.py`

每个节点接收并返回 `State` 对象（即 `dict[str, Any]`），支持以下字段：

| 字段名                          | 类型                    | 描述说明 |
|-------------------------------|------------------------|-----------|
| `locale`                      | `str`                   | 用户语言环境，默认为 `"en-US"` |
| `research_topic`              | `str`                   | 当前研究的主题 |
| `observations`                | `list[str]`             | 已收集的观察结果文本列表 |
| `resources`                   | `list[Resource]`        | 可供智能体参考的资源列表 |
| `plan_iterations`             | `int`                   | 计划迭代次数计数 |
| `current_plan`                | `Plan` 或 `str`          | 当前的执行计划，支持 `Plan` 对象或 JSON 字符串 |
| `final_report`                | `str`                   | 最终报告内容文本 |
| `auto_accepted_plan`          | `bool`                  | 是否自动接受计划，跳过人工反馈 |
| `enable_background_investigation` | `bool`              | 是否开启背景调查功能（网络搜索等） |
| `background_investigation_results` | `str` 或 `None`      | 背景调查的结果文本，可能为空 |
| `instruction`                 | `str`                   | 用户给研究者智能体的额外指令 |
| `focus_info`                  | `dict[str, str]`        | 研究者智能体的重点提示信息字典 |

---

`Resource` 表示一个外部资源对象，通常为智能体在研究任务中可引用的文件、链接或数据集。

| 字段名      | 类型       | 描述                         |
|-------------|------------|------------------------------|
| `uri`       | `str`      | 资源的唯一标识 URI 地址       |
| `title`     | `str`      | 资源的标题                   |
| `description` | `str`或`None` | 资源的描述信息（可选，默认空字符串） |

---

### 2. `Configuration` 配置模型

从 `RunnableConfig["configurable"]` 解析，支持通过环境变量和代码配置传入。

路径：`prompts/configuration.py`

以下是各字段的详细说明：

| 字段名               | 类型              | 默认值           | 描述说明 |
|--------------------|------------------|------------------|-----------|
| `max_plan_iterations` | `int`             | `1`              | 允许 Planner 重试生成计划的最大次数。若超过该次数仍未获得有效计划，将直接进入 `reporter` 或终止。 |
| `max_step_num`        | `int`             | `3`              | 生成计划时允许的最多步骤数。用于限制 Agent 工作负载与控制复杂度。 |
| `max_search_results`  | `int`             | `3`              | 背景调查阶段（如接入 Web Search 工具）最多返回的搜索结果数。 |
| `mcp_settings`        | `dict or None`    | `None`           | MCP 协议配置，用于动态注入远程工具或服务。结构由调用方决定，内部可解析自定义工具链。 |
| `report_style`        | `str` (枚举)      | `"academic"`     | 最终报告风格，支持以下选项：`basic`、`academic`、`popular_science`、`news`、`social_media`。会影响 `reporter` 节点的语言表达方式。 |
| `enable_deep_thinking`| `bool`            | `False`          | 是否开启深度思考模式。在某些 Prompt 中会触发更复杂的推理链条或多轮规划。 |
| `resources`           | `List[Resource]`  | `[]`             | 用户提供的资料文件或链接，可用于研究者节点引用。例如：上传的 PDF、DOCX、网页链接等。 |
| `instruction`         | `str`             | `""`             | 用户在任务开始时的额外指令，将注入到 `researcher` 节点的 Prompt 中，用于限定研究目标。 |
| `focus_info`          | `dict[str, str]`  | `{}`             | Agent 在与用户交互中获得的关注焦点，会被传入 Researcher / Reporter 提示词中，提高上下文相关性。 |

---

### 3. `Plan` / `Step` 模型

`Plan` 是 `planner_node` 节点生成的结构化计划结果，表示当前任务是否具备足够上下文，以及接下来应该如何执行。它在整个智能体工作流中起着关键调度作用，并被 `research_team_node`、`researcher_node`、`coder_node` 等下游节点解析执行。

路径：`prompts/planner_model.py`

---

以下是`Plan`各字段的详细说明：

| 字段名               | 类型              | 描述说明 |
|--------------------|------------------|-----------|
| `locale`             | `str`             | 用户语言环境，如 `"en-US"`、`"zh-CN"`，由系统自动识别或通过 `coordinator_node` 设置 |
| `has_enough_context`| `bool`            | 是否已经有足够的上下文执行报告撰写。若为 `True`，将直接跳转到 `reporter_node` |
| `thought`           | `str`             | LLM 对当前任务的思考过程（即 Chain-of-Thought），主要用于提示词可解释性 |
| `title`             | `str`             | 当前计划的标题，用于在报告和分析阶段展示 |
| `steps`             | `list[Step]`      | 具体执行步骤（由用户或 Agent 决定），每个 `Step` 表示一个需要执行的研究或处理子任务 |

---

以下是`Step`各字段的详细说明：

`steps` 是 `Plan` 中的核心字段，每个 `Step` 表示一次待执行的原子任务，通常由 `researcher_node` 或 `coder_node` 执行。

| 字段名           | 类型              | 描述说明 |
|----------------|------------------|-----------|
| `need_search`   | `bool`            | 是否需要外部搜索支撑（如联网搜索工具） |
| `title`         | `str`             | 当前子任务的简要标题 |
| `description`   | `str`             | 子任务的详细执行描述（指明要收集什么数据、分析什么内容） |
| `step_type`     | `StepType`        | 任务类型，可选值：`research`（研究类）或 `processing`（处理类） |
| `execution_res` | `Optional[str]`   | 子任务执行结果（初始为 `None`，由 Agent 执行后填充） |

---


### 4. Prompt 模板机制

模板目录：`resources/langgraph_prompts/*.md`  
渲染工具：`apply_prompt_template(prompt_name: str, state, config)`

```python
from core.agent.langgraph_agent.prompts.template import apply_prompt_template

messages = apply_prompt_template("planner", state, configurable)
```

模板变量自动注入：

- 所有 `state` 字段
- 所有 `Configuration` 字段
- 当前时间：`CURRENT_TIME`

---

## 🔀 LangGraph 工作流构建

路径：`builder.py`

```python
def build_graph_with_memory(graph_type: str = "base"):
    memory = MemorySaver()
    builder = _build_base_graph()  # 注册节点与边
    return builder.compile(checkpointer=memory)
```

节点注册：

```python
builder.add_node("planner", nodes.planner_node)
builder.add_node("reporter", nodes.reporter_node)
builder.add_conditional_edges(
    "research_team", continue_to_running_research_team, ["planner", "researcher", "coder"]
)
```

---

## 🧩 自定义节点注册机制

在 LangGraph 中，每一个节点代表一次 Agent 执行步骤（如“规划”、“研究”、“代码生成”）。你可以轻松添加自己的自定义节点来处理特定任务。

### 1. 定义自定义节点函数

每个节点函数接受当前 State 和 RunnableConfig（用于获取上下文或配置），返回一个 Command 或更新后的新状态。

最常见的返回值格式为 Command(update=..., goto="下一节点")：

```python
# core/agent/langgraph_agent/nodes.py
from core.agent.langgraph_agent.types import State
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig

async def my_custom_node(state: State, config: RunnableConfig) -> Command:
    user_instruction = state.instruction or "No instruction provided."
    print(f"[my_custom_node] Processing: {user_instruction}")

    # 修改状态并跳转到下一个节点
    return Command(
        update={"observations": state.observations + [f"Handled by custom node: {user_instruction}"]},
        goto="reporter",  # 跳转到下一个阶段
    )
```

### 2. 在工作流中注册节点

```python
# builder.py

from core.agent.langgraph_agent.nodes import my_custom_node

builder.add_node("my_custom_node", my_custom_node)
builder.add_edge("human_feedback", "my_custom_node")
```

---

## 🧠 状态流程图（简化）

```
START
  ↓
coordinator
  ↓
planner ↔ human_feedback
  ↓
research_team ─┬─ researcher
               ├─ coder
               └─ planner (重新规划)
  ↓
reporter
  ↓
END
```

---

## 📦 工具调用（Tool）

### 📁 工具目录结构

```
core/agent/langgraph_agent/tools/
├── __init__.py
├── python_repl.py
```

### ✍️ 定义一个 Tool

使用 `@tool` 装饰器即可注册为 LangChain 工具：

```python
# core/agent/langgraph_agent/tools/python_repl.py
from langchain_core.tools import tool
from typing_extensions import Annotated

@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to do further analysis or calculation."],
) -> str:
    try:
        result = str(eval(code, {"__builtins__": {}}))
        return result
    except Exception as e:
        return f"Error: {e}"
```

使用方式一：绑定到 LLM：

```python
from langchain_openai import ChatOpenAI
from core.agent.langgraph_agent.tools.python_repl import python_repl_tool

llm = ChatOpenAI(model="gpt-4")
llm_with_tools = llm.bind_tools([python_repl_tool])

response = llm_with_tools.invoke("请执行：sum(range(1, 11))")
print(response.content)
```

---

使用方式二：LangGraph 节点中注册工具节点

```python
from langgraph.prebuilt import create_react_agent
from core.agent.langgraph_agent.tools.python_repl import python_repl_tool

tool_node = create_react_agent(model="gpt-4", tools=[python_repl_tool])
builder.add_node("tools", tool_node)
```

---

### 🧹 Tool Response Processor（处理大型工具响应）

定义在 `tool_response_processor.py`，用于应对以下问题：

- 工具输出超过上下文窗口
- 内容冗长导致 LLM 无法处理
- 希望摘要搜索结果或代码块

支持三种策略：

| 策略 | 启用字段 | 说明 |
|------|----------|------|
| 智能摘要 | `enable_summarization=True` | 使用 summarization model 压缩工具输出 |
| 智能分块 | `enable_chunking=True` | 保留结构化信息或摘要重点 |
| 简单截断 | `enable_truncation=True` | 截断内容前后部分保留 |

创建使用：

```python
from langgraph.prebuilt import create_react_agent
from core.agent.langgraph_agent.tools.tool_response_processor import create_tool_response_hook

pre_model_hook = create_tool_response_hook(
    summarization_model=llm,
    enable_summarization=True,
    enable_chunking=True,
    max_tool_response_tokens=3000,
)

tool_node = create_react_agent(model="gpt-4", tools=[python_repl_tool], pre_model_hook=pre_model_hook)
```

---

## 📁 模板目录结构建议

```
resources/langgraph_prompts/
├── coordinator.md
├── planner.md
├── reporter.md
├── researcher.md
└── my_custom_node.md  # 可扩展模板
```

---# 🧠 LangGraph Agent 开发手册

LangGraph Agent 是一个模块化、多节点、状态驱动的 Agent 编排系统，结合了 LangGraph、LangChain、LLM、MCP 工具协议，实现了规划、执行、报告的自动化 Agent 工作流。

---

## 📁 项目结构概览

```
core/agent/langgraph_agent/
├── builder.py                # 构建 LangGraph 工作流图
├── nodes.py                  # 所有 Agent 节点定义
├── prompts/
│   ├── configuration.py      # Configuration 配置模型
│   ├── planner_model.py      # Plan / Step 数据结构
│   ├── report_style.py       # 报告风格枚举
│   └── template.py           # Jinja2 模板渲染工具
├── tools/                    # Agent 工具，如 Python REPL
├── types.py                  # Agent 状态定义
├── utils/                    # 辅助工具，如 JSON 修复
```

---

## ⚙️ 核心组件说明

### 1. `State` 状态模型

`State` 继承自 `MessagesState`，是 LangGraph Agent 运行时的核心上下文状态，保存智能体当前的对话信息、计划、资源和控制标志。

路径：`types.py`

每个节点接收并返回 `State` 对象（即 `dict[str, Any]`），支持以下字段：

| 字段名                          | 类型                    | 描述说明 |
|-------------------------------|------------------------|-----------|
| `locale`                      | `str`                   | 用户语言环境，默认为 `"en-US"` |
| `research_topic`              | `str`                   | 当前研究的主题 |
| `observations`                | `list[str]`             | 已收集的观察结果文本列表 |
| `resources`                   | `list[Resource]`        | 可供智能体参考的资源列表 |
| `plan_iterations`             | `int`                   | 计划迭代次数计数 |
| `current_plan`                | `Plan` 或 `str`          | 当前的执行计划，支持 `Plan` 对象或 JSON 字符串 |
| `final_report`                | `str`                   | 最终报告内容文本 |
| `auto_accepted_plan`          | `bool`                  | 是否自动接受计划，跳过人工反馈 |
| `enable_background_investigation` | `bool`              | 是否开启背景调查功能（网络搜索等） |
| `background_investigation_results` | `str` 或 `None`      | 背景调查的结果文本，可能为空 |
| `instruction`                 | `str`                   | 用户给研究者智能体的额外指令 |
| `focus_info`                  | `dict[str, str]`        | 研究者智能体的重点提示信息字典 |

---

`Resource` 表示一个外部资源对象，通常为智能体在研究任务中可引用的文件、链接或数据集。

| 字段名      | 类型       | 描述                         |
|-------------|------------|------------------------------|
| `uri`       | `str`      | 资源的唯一标识 URI 地址       |
| `title`     | `str`      | 资源的标题                   |
| `description` | `str`或`None` | 资源的描述信息（可选，默认空字符串） |

---

### 2. `Configuration` 配置模型

从 `RunnableConfig["configurable"]` 解析，支持通过环境变量和代码配置传入。

路径：`prompts/configuration.py`

以下是各字段的详细说明：

| 字段名               | 类型              | 默认值           | 描述说明 |
|--------------------|------------------|------------------|-----------|
| `max_plan_iterations` | `int`             | `1`              | 允许 Planner 重试生成计划的最大次数。若超过该次数仍未获得有效计划，将直接进入 `reporter` 或终止。 |
| `max_step_num`        | `int`             | `3`              | 生成计划时允许的最多步骤数。用于限制 Agent 工作负载与控制复杂度。 |
| `max_search_results`  | `int`             | `3`              | 背景调查阶段（如接入 Web Search 工具）最多返回的搜索结果数。 |
| `mcp_settings`        | `dict or None`    | `None`           | MCP 协议配置，用于动态注入远程工具或服务。结构由调用方决定，内部可解析自定义工具链。 |
| `report_style`        | `str` (枚举)      | `"academic"`     | 最终报告风格，支持以下选项：`basic`、`academic`、`popular_science`、`news`、`social_media`。会影响 `reporter` 节点的语言表达方式。 |
| `enable_deep_thinking`| `bool`            | `False`          | 是否开启深度思考模式。在某些 Prompt 中会触发更复杂的推理链条或多轮规划。 |
| `resources`           | `List[Resource]`  | `[]`             | 用户提供的资料文件或链接，可用于研究者节点引用。例如：上传的 PDF、DOCX、网页链接等。 |
| `instruction`         | `str`             | `""`             | 用户在任务开始时的额外指令，将注入到 `researcher` 节点的 Prompt 中，用于限定研究目标。 |
| `focus_info`          | `dict[str, str]`  | `{}`             | Agent 在与用户交互中获得的关注焦点，会被传入 Researcher / Reporter 提示词中，提高上下文相关性。 |

---

### 3. `Plan` / `Step` 模型

`Plan` 是 `planner_node` 节点生成的结构化计划结果，表示当前任务是否具备足够上下文，以及接下来应该如何执行。它在整个智能体工作流中起着关键调度作用，并被 `research_team_node`、`researcher_node`、`coder_node` 等下游节点解析执行。

路径：`prompts/planner_model.py`

---

以下是`Plan`各字段的详细说明：

| 字段名               | 类型              | 描述说明 |
|--------------------|------------------|-----------|
| `locale`             | `str`             | 用户语言环境，如 `"en-US"`、`"zh-CN"`，由系统自动识别或通过 `coordinator_node` 设置 |
| `has_enough_context`| `bool`            | 是否已经有足够的上下文执行报告撰写。若为 `True`，将直接跳转到 `reporter_node` |
| `thought`           | `str`             | LLM 对当前任务的思考过程（即 Chain-of-Thought），主要用于提示词可解释性 |
| `title`             | `str`             | 当前计划的标题，用于在报告和分析阶段展示 |
| `steps`             | `list[Step]`      | 具体执行步骤（由用户或 Agent 决定），每个 `Step` 表示一个需要执行的研究或处理子任务 |

---

以下是`Step`各字段的详细说明：

`steps` 是 `Plan` 中的核心字段，每个 `Step` 表示一次待执行的原子任务，通常由 `researcher_node` 或 `coder_node` 执行。

| 字段名           | 类型              | 描述说明 |
|----------------|------------------|-----------|
| `need_search`   | `bool`            | 是否需要外部搜索支撑（如联网搜索工具） |
| `title`         | `str`             | 当前子任务的简要标题 |
| `description`   | `str`             | 子任务的详细执行描述（指明要收集什么数据、分析什么内容） |
| `step_type`     | `StepType`        | 任务类型，可选值：`research`（研究类）或 `processing`（处理类） |
| `execution_res` | `Optional[str]`   | 子任务执行结果（初始为 `None`，由 Agent 执行后填充） |

---


### 4. Prompt 模板机制

模板目录：`resources/langgraph_prompts/*.md`  
渲染工具：`apply_prompt_template(prompt_name: str, state, config)`

```python
messages = apply_prompt_template("planner", state, configurable)
```

模板变量自动注入：

- 所有 `state` 字段
- 所有 `Configuration` 字段
- 当前时间：`CURRENT_TIME`

---

## 🔀 LangGraph 工作流构建

路径：`builder.py`

```python
def build_graph_with_memory(graph_type: str = "base"):
    memory = MemorySaver()
    builder = _build_base_graph()  # 注册节点与边
    return builder.compile(checkpointer=memory)
```

节点注册：

```python
builder.add_node("planner", nodes.planner_node)
builder.add_node("reporter", nodes.reporter_node)
builder.add_conditional_edges(
    "research_team", continue_to_running_research_team, ["planner", "researcher", "coder"]
)
```

---

## 🧩 自定义节点注册机制

在 LangGraph 中，每一个节点代表一次 Agent 执行步骤（如“规划”、“研究”、“代码生成”）。你可以轻松添加自己的自定义节点来处理特定任务。

### 1. 定义自定义节点函数

每个节点函数接受当前 State 和 RunnableConfig（用于获取上下文或配置），返回一个 Command 或更新后的新状态。

最常见的返回值格式为 Command(update=..., goto="下一节点")：

```python
# core/agent/langgraph_agent/nodes.py
from core.agent.langgraph_agent.types import State
from langgraph.prebuilt.chat_agent_executor import Command
from langchain_core.runnables import RunnableConfig

async def my_custom_node(state: State, config: RunnableConfig) -> Command:
    user_instruction = state.instruction or "No instruction provided."
    print(f"[my_custom_node] Processing: {user_instruction}")

    # 修改状态并跳转到下一个节点
    return Command(
        update={"observations": state.observations + [f"Handled by custom node: {user_instruction}"]},
        goto="reporter",  # 跳转到下一个阶段
    )
```

### 2. 在工作流中注册节点

```python
# builder.py

from core.agent.langgraph_agent.nodes import my_custom_node

builder.add_node("my_custom_node", my_custom_node)
builder.add_edge("human_feedback", "my_custom_node")
```

---

## 🧠 状态流程图（简化）

```
START
  ↓
coordinator
  ↓
planner ↔ human_feedback
  ↓
research_team ─┬─ researcher
               ├─ coder
               └─ planner (重新规划)
  ↓
reporter
  ↓
END
```

---

## 📦 工具调用（Tool）

### 📁 工具目录结构

```
core/agent/langgraph_agent/tools/
├── __init__.py
├── python_repl.py
```

### ✍️ 定义一个 Tool

使用 `@tool` 装饰器即可注册为 LangChain 工具：

```python
# core/agent/langgraph_agent/tools/python_repl.py
from langchain_core.tools import tool
from typing_extensions import Annotated

@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to do further analysis or calculation."],
) -> str:
    try:
        result = str(eval(code, {"__builtins__": {}}))
        return result
    except Exception as e:
        return f"Error: {e}"
```

使用方式一：绑定到 LLM：

```python
from langchain_openai import ChatOpenAI
from core.agent.langgraph_agent.tools.python_repl import python_repl_tool

llm = ChatOpenAI(model="gpt-4")
llm_with_tools = llm.bind_tools([python_repl_tool])

response = llm_with_tools.invoke("请执行：sum(range(1, 11))")
print(response.content)
```

---

使用方式二：LangGraph 节点中注册工具节点

```python
from langgraph.prebuilt import create_react_agent
from core.agent.langgraph_agent.tools.python_repl import python_repl_tool

tool_node = create_react_agent(model="gpt-4", tools=[python_repl_tool])
builder.add_node("tools", tool_node)
```

---

### 🧹 Tool Response Processor（处理大型工具响应）

定义在 `tool_response_processor.py`，用于应对以下问题：

- 工具输出超过上下文窗口
- 内容冗长导致 LLM 无法处理
- 希望摘要搜索结果或代码块

支持三种策略：

| 策略 | 启用字段 | 说明 |
|------|----------|------|
| 智能摘要 | `enable_summarization=True` | 使用 summarization model 压缩工具输出 |
| 智能分块 | `enable_chunking=True` | 保留结构化信息或摘要重点 |
| 简单截断 | `enable_truncation=True` | 截断内容前后部分保留 |

创建使用：

```python
from langgraph.prebuilt import create_react_agent
from core.agent.langgraph_agent.tools.tool_response_processor import create_tool_response_hook

pre_model_hook = create_tool_response_hook(
    summarization_model=llm,
    enable_summarization=True,
    enable_chunking=True,
    max_tool_response_tokens=3000,
)

tool_node = create_react_agent(model="gpt-4", tools=[python_repl_tool], pre_model_hook=pre_model_hook)
```

---

## 📁 模板目录结构建议

```
resources/langgraph_prompts/
├── coordinator.md
├── planner.md
├── reporter.md
├── researcher.md
└── my_custom_node.md  # 可扩展模板
```

---

## 🧠 推荐扩展方向

- ✅ 添加 background investigator 节点，结合搜索引擎
- ✅ 拆分多个 researcher agent（如：市场分析、编程助手、法律分析）
- ✅ 增加摘要器 summarizer 节点
- ✅ 增加 evaluator 节点评估每步结果
- ✅ 支持多语言、多场景报告风格（business, technical）
- ✅ 支持嵌套子图，组合多个 Agent 工作流