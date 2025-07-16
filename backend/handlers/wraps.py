import uuid
from functools import wraps

from core.errors.errcode import Errcode


def validate_uuid_param(*param_indexes):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for index in param_indexes:
                if len(args) > index:
                    param_value = args[index]
                    if not is_valid_uuid(param_value):
                        self.set_status(400)
                        self.write(
                            {
                                "errcode": Errcode.ErrcodeInvalidRequest.value,
                                "msg": f"Invalid UUID at position {index}: {param_value}",
                            }
                        )
                        self.finish()
                        return
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def is_valid_uuid(value):
    try:
        uuid.UUID(value, version=4)
    except ValueError:
        return False
    return True
