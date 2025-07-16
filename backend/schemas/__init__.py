import uuid
from marshmallow import ValidationError


def validate_uuid(value: str):
    if not value:
        return
    try:
        uuid.UUID(value)
    except (ValueError, TypeError):
        raise ValidationError("Invalid UUID format")
