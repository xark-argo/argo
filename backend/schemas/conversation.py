from marshmallow import fields, post_dump

from schemas import validate_uuid
from schemas.bot import AgentModeSchema, AgentToolSchema
from schemas.schemas import BaseSchema


class ConversationItemSchema(BaseSchema):
    id = fields.String(required=True, validate=validate_uuid)
    bot_id = fields.String(required=True, validate=validate_uuid)
    bot_model_config_id = fields.String(required=True, data_key="model_config_id", validate=validate_uuid)
    model_name = fields.String(required=True, data_key="model_id")
    model_provider = fields.String()
    name = fields.String(required=True)
    datasets = fields.Dict(keys=fields.String(), values=fields.List(fields.String()), required=False)
    inputs = fields.Dict(keys=fields.String(), values=fields.String(), required=False)
    tools = fields.List(fields.Nested(AgentToolSchema))
    agent_mode = fields.Nested(AgentModeSchema)

    bot_name = fields.Method("get_bot_name", dump_only=True)
    bot_icon = fields.Method("get_bot_icon", dump_only=True)
    latest_answer = fields.Method("get_latest_answer", dump_only=True)

    @post_dump(pass_original=True)
    def postprocess(self, data, original, **kwargs):
        data["model_name"] = original.model_id
        return data

    def get_bot_name(self, obj):
        bot_info = self.context.get("bots_info", {}).get(obj.bot_id)
        return getattr(bot_info, "name", "") if bot_info else ""

    def get_bot_icon(self, obj):
        bot_info = self.context.get("bots_info", {}).get(obj.bot_id)
        return getattr(bot_info, "icon", "") if bot_info else ""

    def get_latest_answer(self, obj):
        answer = self.context.get("latest_answers", {}).get(obj.id)
        return answer or ""


class GetConversationQuerySchema(BaseSchema):
    last_id = fields.String(required=False, validate=validate_uuid)
    limit = fields.Integer(required=False, load_default=20)


class GetConversationsResponseSchema(BaseSchema):
    has_more = fields.Boolean()
    limit = fields.Integer()
    data = fields.List(fields.Nested(ConversationItemSchema))
