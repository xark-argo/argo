import json

from marshmallow import fields, post_dump

from schemas import validate_uuid
from schemas.schemas import BaseSchema, FileSchema


class MessageItemSchema(BaseSchema):
    id = fields.String(required=True, validate=validate_uuid)
    bot_id = fields.String(required=True, validate=validate_uuid)
    conversation_id = fields.String(required=True, validate=validate_uuid)
    query = fields.String(required=True)
    answer = fields.String(required=True)
    message_tokens = fields.Integer(required=True)
    answer_tokens = fields.Integer(required=True)
    is_stopped = fields.Boolean(required=True)
    files = fields.List(fields.Nested(FileSchema), required=True)
    created_at = fields.DateTime(required=True, format="iso")

    @post_dump(pass_original=True)
    def postprocess(self, data, original, **kwargs):
        data["metadata"] = json.loads(original.message_metadata or "{}")
        data["files"] = getattr(original, "transform_files", [])
        data["agent_thoughts"] = getattr(original, "agent_thoughts_dict", None)
        data["is_stopped"] = getattr(original, "is_stopped", False)
        return data


class GetMessagesQuerySchema(BaseSchema):
    conversation_id = fields.String(
        required=False,
        description="The ID of the conversation to retrieve messages from.",
        validate=validate_uuid,
    )
    first_id = fields.Integer(
        required=False,
        allow_none=True,
        description="The ID of the first message from which to start retrieving.",
        validate=validate_uuid,
    )
    limit = fields.Integer(
        required=False,
        load_default=20,
        description="The number of messages to retrieve. Defaults to 20.",
    )


class GetMessagesResponseSchema(BaseSchema):
    has_more = fields.Boolean(required=True)
    limit = fields.Integer(required=True)
    data = fields.List(fields.Nested(MessageItemSchema), required=True)
