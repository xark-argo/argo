# Model Provider 开发指南

该模块提供了各类模型（如 OpenAI、DeepSeek、Claude 等）的调用、凭据管理和参数规则定义，是 Argo 系统中模型能力的核心桥梁。

通过集中式配置、统一接口规范，**Argo Model Provider 模块**实现了前后端解耦、模型横向扩展、参数规则动态可视化、按需实例化等目标。

---

## ✨ 模块目标

* **供应商和模型配置解耦**：通过 `provider.yaml` 配置实现模型元数据集中管理
* **前端无侵入**：所有模型凭据、参数规则、模型列表均由后端提供，前端通过接口动态渲染
* **支持按需调用**：通过统一 `ModelProviderManager` 工厂创建模型实例
* **易于扩展**：增加新供应商或模型无需改动前后端核心代码

---

## 🧱 模块结构

```text
core/model_providers/
├── manager.py            # Provider 管理类
├── loader.py             # provider.yaml 加载器
├── _position.yaml        # 控制前端展示顺序
├── <provider_name>/
│   └── provider.yaml     # 每个供应商独立的配置文件
```

---

## 📦 provider.yaml 格式说明

每个模型供应商的元信息、凭据规则、参数规则、支持的模型都通过 `provider.yaml` 配置：

### 示例配置：

```yaml
provider: openai
label: OpenAI
description: Official models from OpenAI
icon_url: /api/files/resources/icons/openai.png
color: "#EDF4FC"
position: 1

base_url: https://api.openai.com/v1
class_map:
  chat: langchain_openai.ChatOpenAI
  generate: langchain_openai.OpenAI

api_key_help_message: Get your API Key from OpenAI
api_key_help_url: https://platform.openai.com/account/api-keys

support_chat_models:
  gpt-4o: ["tools", "vision"]
  gpt-3.5-turbo: []

support_embedding_models:
  text-embedding-ada-002: []

parameter_rules:
  - name: temperature
    use_template: temperature
  - name: max_tokens
    use_template: max_tokens
    required: true
    default: 2048
    min: 1
    max: 4096
  - name: api_key
    use_template: api_key
  - name: base_url
    use_template: base_url
```

---

## 🧐 关键概念说明

- `provider`: 唯一标识符
- `label`: 前端显示名称
- `description`: 描述信息
- `icon_url`: 图标路径
- `base_url`: 接口地址
- `class_map`: 模型类型对应的类路径
- `support_chat_models` / `support_embedding_models`: 支持的模型名列表
- `parameter_rules`: 可配置的参数定义
- `api_key_help_message` / `api_key_help_url`: 用于帮助用户获取凭据

### ✅ `support_chat_models` / `support_embedding_models`

* 用于前端展示可选模型列表（灰色表示未配置 API Key）
* 非实际加载模型，仅做 UI 可选模型提示
* key 为 `model_name`，value 为支持的特性列表，如 `tools`、`vision`

### ✅ `parameter_rules`

* 定义模型调用的动态参数（例如 `temperature`、`top_p`）
* 用户填写这些参数后，后端会自动进行 `resolve_parameters` 合并处理
* `use_template` 定义了对应内部模板映射关系

### ✅ `class_map（模型类路径）`

用于指定当前供应商在不同模式下使用的模型类路径：

```yaml
class_map:
  chat: langchain_openai.ChatOpenAI
  generate: langchain_openai.OpenAI
  embedding: langchain_openai.OpenAIEmbeddings
```

> ✅ 开发自定义模型时请注意：
> - `chat` 和 `generate` 模型类需继承自 `langchain_core.language_models.BaseLanguageModel`
> - `embedding` 模型类需继承自 `langchain_core.embeddings.Embeddings`
> 
> 这样可确保模型在框架中被正确识别和加载。


支持模型模式：

Argo 默认支持以下 **模型调用模式** (即 `ModelMode`：)

| 模式         | 描述                   | 示例类                                 |
|--------------|------------------------|----------------------------------------|
| `chat`       | 聊天 / 多轮对话         | `langchain_openai.ChatOpenAI`          |
| `generate`   | 单次文本生成（补全）     | `langchain_openai.OpenAI`              |
| `embedding`  | 文本向量嵌入（Embedding） | `langchain_openai.OpenAIEmbeddings`    |

> 可通过扩展 `ModelMode` 枚举，新增其他模式支持


### ⚠️ 特殊配置限制说明

以下字段一旦配置，**后续不可修改**。  
若需变更，必须手动修改或删除本地 `ARGO_STORAGE_PATH` 路径下的配置数据库 `settings.db`：

- `icon_url`：图标路径，主要用于前端展示供应商 Logo。
- `base_url`：接口地址，定义模型供应商 API 的访问路径。

如需修改，可选择以下方式之一：

- 手动编辑 `ARGO_STORAGE_PATH` 下的 `settings.db` 文件（JSON 格式），或  
- 删除 `settings.db` 文件，系统将自动重新生成（⚠️ 会导致所有模型配置重置）。

请确保首次配置时填写准确。

---

## 🧍️ 如何新增模型供应商

以新增 `deepseek` 为例：

### 第一步：添加配置文件

```bash
mkdir -p core/model_providers/deepseek/
touch core/model_providers/deepseek/provider.yaml
```

### 第二步：添加图标（可选但推荐）

将图标放入以下目录：

```bash
backend/resources/icons/deepseek.png
```

图标路径应在 `provider.yaml` 中通过 `icon_url` 引用：

```yaml
icon_url: /api/files/resources/icons/deepseek.png
```

**图标建议使用 PNG 格式。**  
如果没有现成图标，可以从以下平台查找：

- [LobeHub 图标库](https://lobehub.com/)


### 第三步：安装模型类依赖

```bash
# 如果尚未安装 langchain-deepseek，请运行以下命令
poetry add langchain-deepseek
```

---

## 🛠 使用方式

```python
from core.model_providers import model_provider_manager
from core.model_providers import ModelMode

model_provider_manager.load_all()

# 获取模型实例
model = model_provider_manager.get_model_instance(
    provider="openai",
    model_name="gpt-4o",
    mode=ModelMode.CHAT,
    model_params={
        "api_key": "sk-xxx",
        "temperature": 0.8,
    }
)
```

返回对象是 `langchain_core.language_models.BaseLanguageModel` 子类，可直接调用 `invoke()` 等方法。

---

## 🗃 接口显示顺序

通过 `_position.yaml` 控制：

```yaml
- openai
- deepseek
- anthropic
```

自动加载时使用该顺序对前端展示进行排序

---

## 🧱 ModelProviderSetting（数据库结构）

数据库结构为：

```python
class ModelProviderSetting(BaseModel):
    provider: str
    base_url: str
    api_key: Optional[str]
    support_chat_models: list[ModelInfo]
    ...
```

在启动初始阶段，每个 provider 的运行时配置（如 api_key, base_url）会被存入数据库：

```python
from services.model_provider import initialize_provider_settings

initialize_provider_settings()  # 在 app 启动时调用一次
```

---

如果你是首次参与 Argo 开发，也推荐参考：

* [Argo 项目结构说明](../../../CONTRIBUTING_CN.md)
* [如何贡献 PR](../../../CONTRIBUTING_CN.md)

需要帮助可联系项目 Maintainer 或提交 Issue。
