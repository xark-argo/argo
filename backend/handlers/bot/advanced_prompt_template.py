from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from services.bot.prompt_template import AdvancedPromptTemplateService


class AdvancedPromptTemplateHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request()
    def get(self):
        """
        ---
        tags:
          - Bot
        summary: Retrieve bot prompt template
        description:
          This endpoint retrieves the prompt template for the bot.
          The `has_context` query parameter indicates whether the returned templates contain context information.
        parameters:
          - name: has_context
            in: query
            required: false
            description: Indicates whether the prompt contains context. Defaults to `true`.
            type: boolean
        responses:
          200:
            description: A prompt template was successfully retrieved.
            content:
                application/json:
                    schema:
                      type: object
                      properties:
                        prompt:
                          type: string

          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        has_context = self.get_query_argument("has_context")
        prompt = AdvancedPromptTemplateService.get_prompt(has_context)
        return {"prompt": prompt}


api_router.add("/api/bot/prompt-template", AdvancedPromptTemplateHandler)
