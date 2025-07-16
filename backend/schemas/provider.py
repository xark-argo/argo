from marshmallow import ValidationError, fields, validates_schema

from schemas.schemas import BaseSchema


class CategoryDetailSchema(BaseSchema):
    category = fields.String(required=True)
    label = fields.String()
    prompt = fields.String()
    icon = fields.String()
    icon_color = fields.String()


class CategoryLabelSchema(BaseSchema):
    category = fields.List(fields.Nested(CategoryDetailSchema), required=True)


class CategorySchema(BaseSchema):
    category_label = fields.Nested(CategoryLabelSchema, required=True)


class SimpleModelSchema(BaseSchema):
    model = fields.String(required=True)
    category = fields.Nested(CategorySchema)


class CredentialsSchema(BaseSchema):
    provider = fields.String()
    custom_name = fields.String()

    default_model = fields.String()
    base_url = fields.String()
    api_key = fields.String()
    origin_url = fields.String(allow_none=True)

    support_chat_models = fields.List(fields.Nested(SimpleModelSchema))
    support_embedding_models = fields.List(fields.Nested(SimpleModelSchema))

    description = fields.String()
    link_url = fields.String(allow_none=True)
    color = fields.String(allow_none=True)
    link_msg = fields.String(allow_none=True)
    icon_url = fields.String()

    enable = fields.Integer()

    @validates_schema
    def validate_required_fields(self, data, **kwargs):
        custom_name = data.get("custom_name")
        if not custom_name:
            if not data.get("base_url"):
                raise ValidationError("base_url is required", field_name="base_url")
            if not data.get("api_key"):
                raise ValidationError("api_key is required for", field_name="api_key")


class VerifyProviderSchema(BaseSchema):
    provider = fields.String(required=True)
    credentials = fields.Nested(CredentialsSchema, required=True)
    model_name = fields.String(required=False, allow_none=True)


class AddCustomProviderSchema(BaseSchema):
    provider = fields.String(required=True)
    credentials = fields.Nested(CredentialsSchema, required=True)


class DeleteCustomProviderSchema(BaseSchema):
    provider = fields.String(required=True)


class ProviderItemSchema(BaseSchema):
    provider = fields.String()
    custom_name = fields.String()
    credentials = fields.Nested(CredentialsSchema)
    enable = fields.Integer()


class ProviderListSchema(BaseSchema):
    model_list = fields.List(fields.Nested(ProviderItemSchema))
    not_added_list = fields.List(fields.Nested(ProviderItemSchema))
