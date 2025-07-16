from core.entities.model_entities import APIModelCategory
from core.model_providers.model_category_style import get_model_style
from handlers.base_handler import BaseRequestHandler, RequestHandlerMixin
from handlers.router import api_router


class GetCategoryHandler(BaseRequestHandler, RequestHandlerMixin):
    @RequestHandlerMixin.handle_request()
    def get(self):
        """
        ---
        tags:
          - Workspace
        summary: Get category list
        description: Get category list
        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
        """

        category_data = [
            {
                "type": APIModelCategory.CHAT.value,
                "category": [
                    get_model_style(APIModelCategory.TOOLS.value),
                    get_model_style(APIModelCategory.VISION.value),
                ],
            },
            {
                "type": APIModelCategory.EMBEDDING.value,
                "category": [get_model_style(APIModelCategory.EMBEDDING.value)],
            },
        ]
        return {"msg": category_data}


api_router.add("/api/workspaces/get_category", GetCategoryHandler)
