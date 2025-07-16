import re

REGEX = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]{1,29}|#histories#|#query#|#context#)\}\}")

CONTEXT = "Use the following context as your learned knowledge, \
inside <context></context> XML tags.\n\n<context>\n{{#context#}}\n</context>\n\nWhen \
answer to user:\n- If you don't know, just say that you don't know.\n- If you don't know \
when you are not sure, ask for clarification.\nAvoid mentioning that you obtained the information \
from the context.\nAnd answer according to the language of the user's question.\n"


class PromptTemplateParser:
    """
    Rules:

    1. Template variables must be enclosed in `{{}}`.
    2. The template variable Key can only be: letters + numbers + underscore, with a maximum length of 16 characters,
       and can only start with letters and underscores.
    3. The template variable Key cannot contain new lines or spaces, and must comply with rule 2.
    4. In addition to the above, 3 types of special template variable Keys are accepted:
       `{{#histories#}}` `{{#query#}}` `{{#context#}}`. No other `{{##}}` template variables are allowed.
    """

    def __init__(self, template: str):
        self.template = template
        self.variable_keys = self.extract()

    def extract(self) -> list:
        # Regular expression to match the template rules
        return re.findall(REGEX, self.template)

    def format(self, inputs: dict, remove_template_variables: bool = True) -> str:
        def replacer(match):
            key = match.group(1)
            value = inputs.get(key, match.group(0))  # return original matched string if key not found

            if remove_template_variables:
                return PromptTemplateParser.remove_template_variables(value)
            return value

        return re.sub(REGEX, replacer, self.template)

    @classmethod
    def remove_template_variables(cls, text: str):
        return re.sub(REGEX, r"{\1}", text)
