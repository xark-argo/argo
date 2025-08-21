from marshmallow import fields, post_dump
from marshmallow.validate import Length

from models.bot import BotCategory
from schemas import validate_uuid
from schemas.schemas import BaseSchema, BaseSuccessSchema


class ParagraphSchema(BaseSchema):
    label = fields.String()
    variable = fields.String()
    required = fields.Boolean()
    default = fields.String()
    type = fields.String()


class NumberSchema(BaseSchema):
    label = fields.String()
    variable = fields.String()
    required = fields.Boolean()
    default = fields.String()
    type = fields.String()


class TextInputSchema(BaseSchema):
    label = fields.String()
    variable = fields.String()
    required = fields.Boolean()
    max_length = fields.Integer()
    default = fields.String()
    type = fields.String()


class SelectSchema(BaseSchema):
    label = fields.String()
    variable = fields.String()
    required = fields.Boolean()
    options = fields.List(fields.String())
    default = fields.String()
    type = fields.String()


class UserInputFormItemSchema(BaseSchema):
    paragraph = fields.Nested(ParagraphSchema, required=False)
    text_input = fields.Nested(TextInputSchema, data_key="text-input", required=False)
    select = fields.Nested(SelectSchema)
    number = fields.Nested(NumberSchema, required=False)


class AgentToolSchema(BaseSchema):
    enabled = fields.Boolean()
    id = fields.String()
    doc_ids = fields.List(fields.String())
    type = fields.String()
    description = fields.String()
    name = fields.String()


class AgentModeSchema(BaseSchema):
    enabled = fields.Boolean()
    tools = fields.List(fields.Nested(AgentToolSchema))
    max_iteration = fields.Integer()
    prompt = fields.String(allow_none=True)
    strategy = fields.String(allow_none=True)


class CompletionParamsSchema(BaseSchema):
    temperature = fields.Float(allow_none=True)
    top_p = fields.Float(allow_none=True)
    top_k = fields.Float(allow_none=True)
    repeat_penalty = fields.Float(allow_none=True)
    num_predict = fields.Float(allow_none=True)
    mirostat = fields.Float(allow_none=True)
    mirostat_eta = fields.Float(allow_none=True)
    mirostat_tau = fields.Float(allow_none=True)
    num_ctx = fields.Float(allow_none=True)
    num_gpu = fields.Float(allow_none=True)
    repeat_last_n = fields.Float(allow_none=True)
    tfs_z = fields.Float(allow_none=True)
    stop = fields.List(fields.String(), allow_none=True)


class ModelSchema(BaseSchema):
    provider = fields.String()
    name = fields.String()
    mode = fields.String()
    model_id = fields.String()
    icon_url = fields.String()
    base_url = fields.String()
    link_msg = fields.String()
    link_url = fields.String()
    description = fields.String()
    color = fields.String()
    origin_url = fields.String()
    completion_params = fields.Nested(CompletionParamsSchema)


class ToolConfigItemSchema(BaseSchema):
    tool_type = fields.String()
    provider = fields.String()
    tool_name = fields.String()
    tool_id = fields.String()
    inputs = fields.List(fields.String())
    outputs = fields.List(fields.String())


class TTSPluginSchema(BaseSchema):
    enable = fields.Boolean()
    voice = fields.String()


class Live2DPluginSchema(BaseSchema):
    enable = fields.Boolean()
    model = fields.String()


class PluginConfigSchema(BaseSchema):
    tts = fields.Nested(TTSPluginSchema)
    live2d = fields.Nested(Live2DPluginSchema)


class ModelConfigSchema(BaseSchema):
    provider = fields.String()
    model_id = fields.String()
    configs = fields.Dict()
    model = fields.Nested(ModelSchema)
    user_input_form = fields.List(fields.Nested(UserInputFormItemSchema))
    pre_prompt = fields.String()
    advanced_prompt = fields.String()
    prologue = fields.String()
    agent_mode = fields.Nested(AgentModeSchema)
    prompt_type = fields.String()
    network = fields.Boolean()
    tool_config = fields.List(fields.Nested(ToolConfigItemSchema))
    plugin_config = fields.Nested(PluginConfigSchema)
    silly_character = fields.Dict()

    @post_dump(pass_original=True)
    def postprocess(self, data, original, **kwargs):
        data["model"] = original.model_dict
        data["user_input_form"] = getattr(original, "user_input_form_list", [])
        data["agent_mode"] = getattr(original, "agent_mode_dict", None)
        data["is_stopped"] = getattr(original, "is_stopped", False)
        return data


class SiteSchema(BaseSchema):
    code = fields.String()


class BotSchema(BaseSchema):
    id = fields.String(required=True, validate=validate_uuid)
    space_id = fields.String(required=True, validate=validate_uuid)
    name = fields.String(required=True, validate=Length(min=1, max=50))
    description = fields.String()
    icon = fields.String(load_default="/api/files/resources/icons/bot.jpeg")
    category = fields.String(load_default=BotCategory.ASSISTANT.value)
    status = fields.String(dump_only=True)
    locked = fields.Boolean(dump_only=True)
    background_img = fields.String()
    mode = fields.String(dump_only=True)
    site = fields.Nested(SiteSchema)
    created_at = fields.String(dump_only=True)


class CreateBotSchema(BotSchema):
    id = fields.String(required=True, dump_only=True, validate=validate_uuid)


class GetBotSchema(BotSchema):
    id = fields.String(required=True, validate=validate_uuid)


class BotModelConfigSchema(BotSchema):
    model_config = fields.Nested(
        ModelConfigSchema,
        dump_only=True,
    )

    @post_dump()
    def postprocess(self, data, **kwargs):
        model_config = self.context.get("model_config", {})
        data["model_config"] = model_config
        return data


class ListBotSchema(BaseSchema):
    space_id = fields.String(required=True, validate=validate_uuid)


class DeleteBotSchema(BaseSchema):
    bot_id = fields.String(required=True, validate=validate_uuid)
    space_id = fields.String(required=True, validate=validate_uuid)


class ImportBotsSchema(BaseSchema):
    bots = fields.List(fields.Nested(BotSchema))


class UpdateKnowledgeSchema(BaseSchema):
    bot_id = fields.String(required=True, validate=validate_uuid)
    collection_name = fields.List(fields.String())
    embedding_model = fields.List(fields.String())


class UpdateModelConfigSchema(BaseSchema):
    bot_id = fields.String(required=True, validate=validate_uuid)
    model_config = fields.Nested(
        ModelConfigSchema,
        required=True,
    )


class UpdateModelConfigResponseSchema(BaseSuccessSchema):
    bot_id = fields.String(required=True, validate=validate_uuid)
    config = fields.String(required=True)
    warning_msg = fields.String()


bot_schema = BotSchema()
bot_model_config_schema = BotModelConfigSchema()
