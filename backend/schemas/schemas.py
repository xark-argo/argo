from marshmallow import EXCLUDE, Schema, fields


class BaseSchema(Schema):
    class Meta:
        ordered = True
        unknown = EXCLUDE


class BaseErrorSchema(BaseSchema):
    errcode = fields.Integer(required=True)
    msg = fields.String(required=True)


class BaseSuccessSchema(BaseSchema):
    errcode = fields.Constant(-1, required=True, description="-1 indicates success")
    msg = fields.String(required=True, description="Success message")


class FileSchema(BaseSchema):
    id = fields.String()
    type = fields.String()
    name = fields.String()
    transfer_method = fields.String()
    url = fields.String()
