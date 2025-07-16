from core.i18n.translation import translation_loader
from handlers.base_handler import BaseRequestHandler, RequestHandlerMixin
from handlers.router import api_router


class AboutHandler(BaseRequestHandler, RequestHandlerMixin):
    @RequestHandlerMixin.handle_request()
    def get(self):
        """
        ---
        tags: [Workspace]
        summary: Get update log
        description: Get update log

        responses:
          200:
            description: Message sent successfully
            schema:
              type: object
              properties:
                errcode:
                  type: integer
        """

        return {
            "msg": translation_loader.translation.generate_log(),
            "version": translation_loader.translation.t("version"),
            "window_size": float(translation_loader.translation.t("package_size.window_size")),
            "mac_size": float(translation_loader.translation.t("package_size.mac_size")),
        }


api_router.add("/api/workspaces/get_changelog", AboutHandler)
