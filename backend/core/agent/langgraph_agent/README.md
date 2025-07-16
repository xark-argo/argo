# 🧠 LangGraph Agent Development Manual

LangGraph Agent is a modular, multi-node, state-driven agent orchestration system that integrates LangGraph, LangChain, LLM, and MCP tool protocols to realize automated workflows for planning, execution, and reporting.

---

## 📁 Project Structure Overview

```
core/agent/langgraph_agent/
├── builder.py                # Build LangGraph workflow graph
├── nodes.py                  # Agent node definitions
├── prompts/
│   ├── configuration.py      # Configuration model
│   ├── planner_model.py      # Plan / Step data structure
│   ├── report_style.py       # Report style enum
│   └── template.py           # Jinja2 template renderer
├── tools/                    # Agent tools, e.g., Python REPL
├── types.py                  # Agent state definition
├── utils/                    # Utilities, e.g., JSON fixer
```

---

## ⚙️ Core Components Description

### 1. `State` State Model

`State` inherits from `MessagesState`, serving as the core runtime context state for LangGraph Agent, storing the agent's current conversation, plan, resources, and control flags.

Path: `types.py`

Each node receives and returns a `State` object (i.e., `dict[str, Any]`), supporting the following fields:

| Field Name                    | Type                   | Description                               |
|------------------------------|------------------------|------------------------------------------|
| `locale`                     | `str`                  | User locale, default is `"en-US"`        |
| `research_topic`             | `str`                  | Current research topic                    |
| `observations`               | `list[str]`            | List of collected observation texts      |
| `resources`                  | `list[Resource]`       | List of resources available for reference|
| `plan_iterations`            | `int`                  | Plan iteration count                      |
| `current_plan`               | `Plan` or `str`        | Current execution plan, supports `Plan` object or JSON string |
| `final_report`               | `str`                  | Final report content text                 |
| `auto_accepted_plan`         | `bool`                 | Whether to auto-accept the plan, skipping manual feedback |
| `enable_background_investigation` | `bool`           | Whether to enable background investigation (e.g., web search) |
| `background_investigation_results` | `str` or `None`   | Background investigation results text, possibly empty |
| `instruction`                | `str`                  | Additional user instructions for the researcher agent |
| `focus_info`                 | `dict[str, str]`       | Focus hints dictionary for the researcher agent |

---

`Resource` represents an external resource object, typically a file, link, or dataset that the agent can reference during research tasks.

| Field Name      | Type         | Description                              |
|-----------------|--------------|-----------------------------------------|
| `uri`           | `str`        | Unique resource URI identifier          |
| `title`         | `str`        | Resource title                          |
| `description`   | `str` or `None` | Optional resource description (default empty string) |

---

### 2. `Configuration` Configuration Model

Parsed from `RunnableConfig["configurable"]`, supports configuration via environment variables or code.

Path: `prompts/configuration.py`

Detailed field descriptions:

| Field Name            | Type             | Default        | Description                                                    |
|-----------------------|------------------|----------------|----------------------------------------------------------------|
| `max_plan_iterations` | `int`             | `1`            | Max retries for planner to generate a valid plan. Exceeding this jumps to `reporter` or terminates. |
| `max_step_num`        | `int`             | `3`            | Max steps allowed when generating a plan, to limit workload and complexity. |
| `max_search_results`  | `int`             | `3`            | Max search results returned during background investigation (e.g., Web Search). |
| `mcp_settings`        | `dict` or `None`  | `None`         | MCP protocol config for dynamic remote tool injection, structure decided by caller. |
| `report_style`        | `str` (enum)      | `"academic"`   | Final report style; options include `basic`, `academic`, `popular_science`, `news`, `social_media`. Affects reporter node language style. |
| `enable_deep_thinking`| `bool`            | `False`       | Enable deep thinking mode for complex reasoning chains or multi-round planning. |
| `resources`           | `List[Resource]`  | `[]`           | User-provided files or links for researcher node references (e.g., PDFs, DOCXs, web links). |
| `instruction`         | `str`             | `""`           | Additional user instructions injected into researcher prompt to constrain research goals. |
| `focus_info`          | `dict[str, str]`  | `{}`           | Focus points from user interaction, passed into Researcher / Reporter prompts to improve context relevance. |

---

### 3. `Plan` / `Step` Model

`Plan` is the structured plan result generated by `planner_node`, indicating if the task has enough context and how to proceed next. It is a key orchestrator parsed and executed by downstream nodes like `research_team_node`, `researcher_node`, `coder_node`.

Path: `prompts/planner_model.py`

---

`Plan` field details:

| Field Name            | Type          | Description                                           |
|-----------------------|---------------|-------------------------------------------------------|
| `locale`              | `str`         | User locale such as `"en-US"` or `"zh-CN"`, auto detected or set by `coordinator_node` |
| `has_enough_context`  | `bool`        | Whether enough context exists to directly write report; if true, jumps to `reporter_node` |
| `thought`             | `str`         | LLM chain-of-thought reasoning for interpretability   |
| `title`               | `str`         | Plan title for reporting and analysis                  |
| `steps`               | `list[Step]`  | Specific execution steps (determined by user or agent), each `Step` is a research or processing subtask |

---

`Step` field details:

Each `Step` in the plan represents an atomic task usually executed by `researcher_node` or `coder_node`.

| Field Name       | Type            | Description                                                |
|------------------|-----------------|------------------------------------------------------------|
| `need_search`    | `bool`          | Whether external search support is needed (e.g., web search tools) |
| `title`          | `str`           | Brief title of the subtask                                  |
| `description`    | `str`           | Detailed execution description (what data to collect, analyze) |
| `step_type`      | `StepType`      | Task type: `research` (research) or `processing` (processing) |
| `execution_res`  | `Optional[str]` | Execution result of the subtask (initially `None`, filled after execution) |

---

### 4. Prompt Template Mechanism

Template directory: `resources/langgraph_prompts/*.md`  
Rendering utility: `apply_prompt_template(prompt_name: str, state, config)`

Example usage:

```python
from core.agent.langgraph_agent.prompts.template import apply_prompt_template

messages = apply_prompt_template("planner", state, configurable)
```

Template variables automatically injected:

- All `state` All
- All `Configuration` All
- Current time：`CURRENT_TIME`

---

## 🔀 LangGraph Workflow Construction

Path：`builder.py`

```python
def build_graph_with_memory(graph_type: str = "base"):
    memory = MemorySaver()
    builder = _build_base_graph()  # Register nodes and edges
    return builder.compile(checkpointer=memory)
```

Node registration：

```python
builder.add_node("planner", nodes.planner_node)
builder.add_node("reporter", nodes.reporter_node)
builder.add_conditional_edges(
    "research_team", continue_to_running_research_team, ["planner", "researcher", "coder"]
)
```

---

## 🧩 Custom Node Registration Mechanism

In LangGraph, each node represents an agent execution step (e.g., “planning,” “research,” “code generation”). You can easily add custom nodes to handle specific tasks.

### 1. Define a custom node function

Each node function accepts the current State and RunnableConfig (for context/config), returning a Command or updated new state.

Common return format is Command(update=..., goto="next_node"):

```python
# core/agent/langgraph_agent/nodes.py
from core.agent.langgraph_agent.types import State
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig

async def my_custom_node(state: State, config: RunnableConfig) -> Command:
    user_instruction = state.instruction or "No instruction provided."
    print(f"[my_custom_node] Processing: {user_instruction}")

    # Modify state and jump to the next node
    return Command(
        update={"observations": state.observations + [f"Handled by custom node: {user_instruction}"]},
        goto="reporter",  # Jump to next stage
    )
```

### 2. Register node in the workflow

```python
# builder.py

from core.agent.langgraph_agent.nodes import my_custom_node

builder.add_node("my_custom_node", my_custom_node)
builder.add_edge("human_feedback", "my_custom_node")
```

---

## 🧠 Simplified State Flowchart

```
START
  ↓
coordinator
  ↓
planner ↔ human_feedback
  ↓
research_team ─┬─ researcher
               ├─ coder
               └─ planner (replan)
  ↓
reporter
  ↓
END
```

---

## 📦 Tool Invocation

### 📁 Tool directory structure

```
core/agent/langgraph_agent/tools/
├── __init__.py
├── python_repl.py
```

### ✍️ Define a Tool

Use the `@tool` decorator to register a LangChain tool:

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

Use case 1: Bind to LLM:

```python
from langchain_openai import ChatOpenAI
from core.agent.langgraph_agent.tools.python_repl import python_repl_tool

llm = ChatOpenAI(model="gpt-4")
llm_with_tools = llm.bind_tools([python_repl_tool])

response = llm_with_tools.invoke("Please execute: sum(range(1, 11))")
print(response.content)
```

---

Use case 2: Register tool node in LangGraph:

```python
from langgraph.prebuilt import create_react_agent
from core.agent.langgraph_agent.tools.python_repl import python_repl_tool

tool_node = create_react_agent(model="gpt-4", tools=[python_repl_tool])
builder.add_node("tools", tool_node)
```

---

### 🧹 Tool Response Processor (handling large tool outputs)

Defined in `tool_response_processor.py` to address:

- Tool outputs exceeding context window
- Lengthy content preventing LLM processing
- Desire to summarize search results or code blocks

支持三种策略：

| Strategy | Enable Field | Description |
|--|----------|------|
| Smart Summarize | `enable_summarization=True` | Use summarization model to compress tool output |
| Smart Chunking | `enable_chunking=True` | Preserve structure or summary highlights |
| Simple Truncation | `enable_truncation=True` | Truncate content, preserving head and tail |

Usage example：

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

## 📁 Recommended Template Directory Structure

```
resources/langgraph_prompts/
├── coordinator.md
├── planner.md
├── reporter.md
├── researcher.md
└── my_custom_node.md  # Extensible templates
```

---

## 🧠 Recommended Extension Directions

- ✅ Add background investigator node, integrating search engines
- ✅ Split multiple researcher agents (e.g., market analysis, programming assistant, legal analysis)
- ✅ Add summarizer node
- ✅ Add evaluator node to assess each step result
- ✅ Support multi-language, multi-scenario report styles (business, technical)
- ✅ Support nested subgraphs, composing multiple agent workflows