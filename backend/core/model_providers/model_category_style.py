from core.entities.model_entities import APIModelCategory
from core.i18n.translation import translation_loader


def get_model_style(category: str = "") -> dict:
    if category == APIModelCategory.TOOLS.value:
        return {
            "category": APIModelCategory.TOOLS.value,
            "label": translation_loader.translation.t("provider.category_info.tool.label"),
            "prompt": translation_loader.translation.t("provider.category_info.tool.prompt"),
            "icon": "/api/files/resources/icons/tool.svg",
            "icon_color": "/api/files/resources/icons/tool_color.svg",
        }
    elif category == APIModelCategory.VISION.value:
        return {
            "category": APIModelCategory.VISION.value,
            "label": translation_loader.translation.t("provider.category_info.vision.label"),
            "prompt": translation_loader.translation.t("provider.category_info.vision.prompt"),
            "icon": "/api/files/resources/icons/vision.svg",
            "icon_color": "/api/files/resources/icons/vision_color.svg",
        }
    elif category == APIModelCategory.EMBEDDING.value:
        return {
            "category": APIModelCategory.EMBEDDING.value,
            "label": translation_loader.translation.t("provider.category_info.embedding.label"),
            "prompt": translation_loader.translation.t("provider.category_info.embedding.prompt"),
            "icon": "/api/files/resources/icons/embedding.svg",
            "icon_color": "/api/files/resources/icons/embedding_color.svg",
        }
    raise Exception("Unknown model category.")
