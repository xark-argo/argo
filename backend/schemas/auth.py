from marshmallow import fields

from schemas.schemas import BaseSchema


class LoginSchema(BaseSchema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class RegisterSchema(BaseSchema):
    email = fields.Email(required=True)
    password = fields.String(required=True)
    username = fields.String(required=True)
