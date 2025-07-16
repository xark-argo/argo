from marshmallow import fields
from marshmallow.validate import Length

from schemas import validate_uuid
from schemas.schemas import BaseSchema


class WorkspaceMemberSchema(BaseSchema):
    id = fields.String(required=True, validate=validate_uuid, description="Member ID")
    name = fields.String(required=True, attribute="username", description="Member name")
    email = fields.Email(required=True, description="Member email")
    created_at = fields.String(required=True, description="Creation timestamp in ISO format")
    role = fields.String(required=True, description="Role of the member")
    status = fields.String(required=True, description="Status of the member")


class AddMemberSchema(BaseSchema):
    email = fields.Email(required=True, description="The member's email address")
    role = fields.String(required=True, validate=Length(min=1), description="The role of the member")


class DeleteMemberSchema(BaseSchema):
    user_id = fields.String(
        required=True,
        validate=validate_uuid,
        description="The UUID of the user to be deleted",
    )
