import inspect
import json
import logging
from functools import wraps
from typing import Any, Optional, cast

import tornado
from marshmallow import Schema, ValidationError
from tornado import web
from tornado.iostream import StreamClosedError

from core.errors.errcode import Errcode
from core.errors.notfound import NotFoundError
from core.errors.validate import ValidateError
from core.i18n.translation import translation_loader
from models.user import User, get_user
from services.auth.auth_service import AuthService


class AppError(Exception):
    """业务逻辑错误"""

    def __init__(self, message, errcode=Errcode.ErrcodeInvalidRequest.value, status=400):
        self.message = message
        self.errcode = errcode
        self.status = status
        super().__init__(message)


class BaseRequestHandler(web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.required_fields = []
        self.req_dict = {}
        super().__init__(*args, **kwargs)

    def prepare(self):
        if self.request.method == "GET":
            return
        if self.request.headers.get("Content-Type", "").startswith("multipart/form-data"):
            return
        if not self.request.body:
            return
        logging.info(
            f"request api: {self.request.uri}, request body: {self.request.body.decode('utf-8', errors='ignore')}"
        )
        self.req_dict = tornado.escape.json_decode(self.request.body)
        for field in self.required_fields:
            if field not in self.req_dict:
                self.set_status(400)
                self.write(
                    {
                        "errcode": Errcode.ErrcodeInvalidRequest.value,
                        "msg": translation_loader.translation.t("file.missing_required_field", field=field),
                    }
                )
                self.finish()
                return

    def write(self, chunk) -> None:
        # if isinstance(chunk, dict):
        #     if self.request.uri not in ['/healthcheck', '/api/chat/say'] and \
        #             (self.request.uri != '/api/model/get_model_list' or random.random() < 0.1) and \
        #             (self.request.uri not in ['/api/tts/tts', '/api/tts/voices']):
        #         logging.info(f"request api: {self.request.uri}, response body: {chunk}")
        super().write(chunk)

    def get_current_user(self) -> Optional[User]:
        auth_header = self.request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        if not token:
            return None

        current_user = AuthService.decode_token(token)
        user_id = current_user.get("id") if isinstance(current_user, dict) else None

        return get_user(user_id) if user_id else None


class RequestHandlerMixin:
    validated_data: dict
    _handler: Optional[web.RequestHandler] = None

    def _cast_self(self) -> web.RequestHandler:
        return cast(web.RequestHandler, self)

    @property
    def handler(self) -> web.RequestHandler:
        if self._handler is None:
            self._handler = cast(web.RequestHandler, self)
        return self._handler

    def _extract_request_data(self, query: Optional[bool]) -> dict:
        handler = self._cast_self()
        method = (handler.request.method or "").upper()
        use_query = query if query is not None else method == "GET"

        if use_query:
            return {k: v[0].decode() if isinstance(v, list) else v for k, v in handler.request.query_arguments.items()}

        return getattr(handler, "req_dict", {})

    def _handle_error(self, status_code: int, errcode: int, message: str):
        self.handler.set_status(status_code)
        self.handler.set_header("Content-Type", "application/json")
        self.handler.write(json.dumps({"errcode": errcode, "msg": message}, ensure_ascii=False))
        self.handler.finish()

    async def _write_response(self, result: Optional[Any]):
        try:
            if inspect.isawaitable(result):
                result = await result

            if result is None:
                self.handler.set_status(200)
                return await self.handler.finish()

            if isinstance(result, (dict, str, bytes)):
                self.handler.set_status(200)
                self.handler.set_header("Content-Type", "application/json")
                self.handler.write(result)
                return await self.handler.finish()

            if inspect.isgenerator(result) or inspect.isasyncgen(result):
                self.handler.set_status(200)
                self.handler.set_header("Content-Type", "text/event-stream")
                self.handler.set_header("Cache-Control", "no-cache")
                self.handler.set_header("X-Accel-Buffering", "no")

                try:
                    if inspect.isgenerator(result):
                        for chunk in result:
                            if inspect.isawaitable(chunk):
                                chunk = await chunk
                            self.handler.write(chunk)
                            await self.handler.flush()
                    else:
                        async for chunk in result:
                            if inspect.isawaitable(chunk):
                                chunk = await chunk
                            self.handler.write(chunk)
                            await self.handler.flush()
                except StreamClosedError:
                    logging.warning("Stream closed by client")
                    return

                return await self.handler.finish()

            return self._handle_error(
                500,
                Errcode.ErrcodeInternalServerError.value,
                f"Unsupported return type: {type(result)}",
            )

        except StreamClosedError:
            logging.warning("Client closed the connection during response")
        except Exception as e:
            logging.exception("Error in _write_response")
            return self._handle_error(500, Errcode.ErrcodeInternalServerError.value, str(e))

    @classmethod
    def handle_request(cls, schema_cls: Optional[type[Schema]] = None, query: Optional[bool] = None):
        def decorator(method):
            @wraps(method)
            async def wrapper(self, *args, **kwargs):
                try:
                    data = self._extract_request_data(query)
                    self.validated_data = schema_cls().load(data) if schema_cls else data

                    is_async = inspect.iscoroutinefunction(method)
                    result = await method(self, *args, **kwargs) if is_async else method(self, *args, **kwargs)
                    await self._write_response(result)

                except ValidationError as ve:
                    return self._handle_error(400, Errcode.ErrcodeInvalidRequest.value, str(ve.messages))
                except ValidateError as e:
                    return self._handle_error(400, Errcode.ErrcodeInvalidRequest.value, str(e))
                except NotFoundError as e:
                    return self._handle_error(404, Errcode.ErrcodeRequestNotFound.value, str(e))
                except AppError as ae:
                    return self._handle_error(ae.status, ae.errcode, ae.message)
                except Exception as e:
                    logging.exception("Internal Server Error")
                    return self._handle_error(500, Errcode.ErrcodeInternalServerError.value, str(e))

            return wrapper

        return decorator


class BaseProtectedHandler(RequestHandlerMixin, BaseRequestHandler):
    current_user: User

    def prepare(self):
        # 在每个请求之前调用，进行用户鉴权
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"errcode": Errcode.ErrcodeUnauthorized.value, "msg": "Unauthorized"})
            self.finish()
            return
        self.current_user = user
        super().prepare()
