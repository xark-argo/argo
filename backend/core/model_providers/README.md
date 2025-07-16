# Model Provider Development Guide

This module provides the core bridge for invoking models (e.g., OpenAI, DeepSeek, Claude), managing credentials, and defining parameter rules. It is a central part of Argo’s model capabilities.

Through centralized configuration and unified interface standards, the **Argo Model Provider module** enables frontend-backend decoupling, horizontal model scalability, dynamic visualization of parameter rules, and on-demand instantiation.

---

## ✨ Module Goals

* **Decoupling provider and model config**: Centralized model metadata management via `provider.yaml`
* **Frontend-agnostic**: All credentials, parameter rules, and model lists are provided by the backend; frontend renders dynamically via APIs
* **On-demand usage support**: Models are instantiated via a unified `ModelProviderManager` factory
* **Easy extensibility**: Adding new providers or models requires no changes to core frontend or backend code

---

## 🧱 Module Structure

```text
core/model_providers/
├── manager.py            # Provider manager class
├── loader.py             # provider.yaml loader
├── _position.yaml        # Controls frontend display order
├── <provider_name>/
│   └── provider.yaml     # Individual config file per provider
```

---

## 📦 `provider.yaml` Format Explained

Each provider’s metadata, credential rules, parameter rules, and supported models are defined in `provider.yaml`.

### Example Config:

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

## 🧐 Key Concepts Explained

- `provider`: Unique identifier
- `label`: Display name in UI
- `description`: Provider description
- `icon_url`: Path to icon file
- `base_url`: API base URL
- `class_map`: Class paths for different model modes (must inherit from `langchain_core.language_models.BaseLanguageModel`)
- `support_chat_models` / `support_embedding_models`: List of supported model names
- `parameter_rules`: Configurable parameter definitions
- `api_key_help_message` / `api_key_help_url`: Guides for users to retrieve API keys

### ✅ `support_chat_models` / `support_embedding_models`

* Used for UI to display selectable model lists (greyed out if API key not set)
* These do not actually load models, only used for UI selection hints
* Keys are `model_name`, values are lists of supported features like `tools`, `vision`

### ✅ `parameter_rules`

* Defines dynamic parameters for model invocation (e.g., `temperature`, `top_p`)
* Once filled by the user, backend will auto-merge them via `resolve_parameters`
* `use_template` maps to internal logic templates

### ✅ `class_map` (Model Class Mapping)

Specifies the model class paths used by the current provider in different modes:

```yaml
class_map:
  chat: langchain_openai.ChatOpenAI
  generate: langchain_openai.OpenAI
  embedding: langchain_openai.OpenAIEmbeddings
```

> ✅ When developing custom models, please ensure:
> - `chat` and `generate` model classes must inherit from `langchain_core.language_models.BaseLanguageModel`
> - `embedding` model classes must inherit from `langchain_core.embeddings.Embeddings`
> 
> This ensures that models are correctly recognized and loaded by the framework.

Supported Model Modes:

Argo supports the following **model invocation modes** by default (i.e., `ModelMode`):

| Mode        | Description                 | Example Class                        |
|-------------|-----------------------------|------------------------------------|
| `chat`      | Chat / Multi-turn Conversation | `langchain_openai.ChatOpenAI`      |
| `generate`  | Single Text Generation (Completion) | `langchain_openai.OpenAI`          |
| `embedding` | Text Vector Embedding         | `langchain_openai.OpenAIEmbeddings` |

> You can extend the `ModelMode` enum to support additional modes.


### ⚠️ Special Configuration Constraints

The following fields **cannot be modified once configured**.  
To change them, you must manually update or delete the local settings database located at `ARGO_STORAGE_PATH`:

- `icon_url`: Path to the icon, used primarily for displaying the provider’s logo in the frontend.
- `base_url`: API endpoint that defines the access path to the model provider.

If a change is necessary, you can:

- Manually edit the `settings.db` file (a JSON file) under `ARGO_STORAGE_PATH`, or  
- Delete the `settings.db` file to regenerate it with new values.

Please ensure these fields are set correctly during the initial configuration.

---

## 🧍️ How to Add a New Model Provider

Using `deepseek` as an example:

### Step 1: Add Configuration File

```bash
mkdir -p core/model_providers/deepseek/
touch core/model_providers/deepseek/provider.yaml
```

### Step 2: Add Icon (Optional but Recommended)

Place the icon into:

```bash
backend/resources/icons/deepseek.png
```

Reference it in `provider.yaml` via `icon_url`:

```yaml
icon_url: /api/files/resources/icons/deepseek.png
```

**PNG format is recommended.**  
If you don’t have one, try searching on:

- [LobeHub Icon Library](https://lobehub.com/)

### Step 3: Install Model Class Dependency

```bash
# Skip this step if the package is already installed.
poetry add langchain-deepseek
```

---

## 🛠 Usage Example

```python
from core.model_providers import model_provider_manager
from core.model_providers import ModelMode

model_provider_manager.load_all()

# Get model instance
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

The returned object is a subclass of `langchain_core.language_models.BaseLanguageModel` and supports methods like `invoke()`.

---

## 🗃 Display Order on UI

Controlled via `_position.yaml`:

```yaml
- openai
- deepseek
- anthropic
```

Frontend uses this order to render providers.

---

## 🧱 ModelProviderSetting (Database Structure)

Database structure looks like:

```python
class ModelProviderSetting(BaseModel):
    provider: str
    base_url: str
    api_key: Optional[str]
    support_chat_models: list[ModelInfo]
    ...
```

At initialization, each provider’s runtime config (e.g., `api_key`, `base_url`) is persisted into the database via:

```python
from services.model_provider import initialize_provider_settings

initialize_provider_settings()  # Call once during app startup
```

---

If this is your first time contributing to Argo, we recommend checking out:

* [Argo Project Structure](../../../CONTRIBUTING.md)
* [How to Contribute PRs](../../../CONTRIBUTING.md)

Need help? Contact a project maintainer or open an issue.