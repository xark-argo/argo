from marshmallow import fields

from schemas.schemas import BaseSchema


class ConfigItemSchema(BaseSchema):
    enable_multi_user = fields.Boolean(required=True)
