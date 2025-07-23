from marshmallow import Schema, fields

from schemas import validate_uuid
from schemas.bot import ModelConfigSchema
from schemas.schemas import BaseSchema, FileSchema


class SayChatSchema(BaseSchema):
    invoke_from = fields.String(validate=lambda x: x in ["web-app", "debugger"])
    bot_id = fields.String(required=True, validate=validate_uuid)
    conversation_id = fields.String(required=False, validate=validate_uuid)
    message = fields.String(required=True)
    stream = fields.Boolean()
    space_id = fields.String(required=False, validate=validate_uuid)
    regen_message_id = fields.String(required=False, validate=validate_uuid)
    inputs = fields.Dict(keys=fields.String(), values=fields.String())
    files = fields.List(fields.Nested(FileSchema))
    mode = fields.String()

    model_config = fields.Nested(ModelConfigSchema())


class WebSayChatSchema(BaseSchema):
    invoke_from = fields.String(validate=lambda x: x in ["web-app", "debugger"])
    conversation_id = fields.String(required=False, validate=validate_uuid)
    message = fields.String(required=True)
    stream = fields.Boolean()
    regen_message_id = fields.String(required=False, validate=validate_uuid)
    mode = fields.String()


class StopChatSchema(BaseSchema):
    task_id = fields.String(required=True, validate=validate_uuid)
    message_id = fields.String(required=True, validate=validate_uuid)


class PromptMessageSchema(BaseSchema):
    role = fields.String()
    text = fields.String()


class GetPromptMessagesResponseSchema(BaseSchema):
    data = fields.Nested(Schema.from_dict({"prompt_messages": fields.List(fields.Nested(PromptMessageSchema))})())
