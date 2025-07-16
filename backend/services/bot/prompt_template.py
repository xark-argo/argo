import copy
from typing import Optional

CONTEXT = "Use the following context as your learned knowledge, \
inside <context></context> XML tags.\n\n<context>\n{{#context#}}\n</context>\n\nWhen \
answer to user:\n- If you don't know, just say that you don't know.\n- If you don't know \
when you are not sure, ask for clarification.\nAvoid mentioning that you obtained the information \
from the context.\nAnd answer according to the language of the user's question.\n"


class AdvancedPromptTemplateService:
    @staticmethod
    def get_prompt(has_context: Optional[str]) -> str:
        prompt_template = "{{#pre_prompt#}}"
        if has_context == "true":
            context_prompt = copy.deepcopy(CONTEXT)
            prompt_template = context_prompt + prompt_template

        return prompt_template
