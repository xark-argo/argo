from .auth import auth_handler
from .bot import advanced_prompt_template, bot_handler, knowledge_update, model_config
from .chat import chat_handler, conversation, message
from .doc import (
    bind_space,
    bot_install,
    bot_status_query,
    create_collection,
    create_temp_knowledge,
    drop_collection,
    drop_partition,
    get_directory,
    list_collections,
    list_datasets,
    list_documents,
    restore_document,
    unbind_space,
    update_collection,
    upload_documents,
    upload_url,
)
from .tool import (
    check_mcp,
    create_mcp,
    delete_mcp,
    get_mcp_list,
    mcp_tool_install,
    mcp_tool_install_status,
    update_mcp,
)
from .file import file_delete, file_upload, file_web
from .healthcheck import health_check
from .model import (
    change_model_category,
    change_model_status,
    clean_model_cache,
    delete_model,
    download_model,
    download_model_ollama,
    get_model_info,
    get_model_list,
    get_popular_model,
    ollama_service_check,
    parse_model_url,
    update_model_name,
)
from .tts import tts_handler
from .workspace import (
    about,
    get_category_list,
    model_providers,
    members_handler,
    provider_models,
    set_language,
    verify_providers,
    workspace_handler,
)

from .config import config_handler


# isort: off
# from . import static_handler must come last
from .static import static_handler
