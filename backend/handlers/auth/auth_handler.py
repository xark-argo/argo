from core.entities.user_entities import UserType
from core.errors.errcode import Errcode
from handlers.base_handler import (
    AppError,
    BaseRequestHandler,
    RequestHandlerMixin,
)
from handlers.router import api_router
from schemas.auth import GuestTokenSchema, LoginSchema, RegisterSchema
from services.auth.auth_service import AuthService


class LoginHandler(RequestHandlerMixin, BaseRequestHandler):
    @RequestHandlerMixin.handle_request(LoginSchema)
    def post(self):
        """
        ---
        tags: [Auth]
        summary: User login
        description: Authenticate user and return JWT token

        requestBody:
            description: Login data
            required: True
            content:
                application/json:
                    schema:
                        LoginSchema

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                      type: object
                      properties:
                        token:
                            type: string

          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        user = AuthService.login(self.validated_data["email"], self.validated_data["password"])
        if user:
            token = AuthService.generate_token(user)
            return {"token": token}
        else:
            raise AppError("Invalid email or password", Errcode.ErrcodeInvalidRequest.value, 401)


class GuestTokenHandler(RequestHandlerMixin, BaseRequestHandler):
    @RequestHandlerMixin.handle_request(GuestTokenSchema)
    def post(self):
        """
        ---
        tags: [Auth]
        summary: Obtain guest user token
        description: Log in as a guest using a verification code and receive a JWT token.

        requestBody:
            required: True
            content:
                application/json:
                    schema:
                        GuestTokenSchema

        responses:
          200:
            description: Login success
            content:
                application/json:
                    schema:
                      type: object
                      properties:
                        token:
                          type: string

          400:
            description: Invalid input or code
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        user = AuthService.create_guest_user_by_code(self.validated_data["code"])
        if user:
            token = AuthService.generate_token(user, UserType.GUEST)
            return {"token": token}
        else:
            raise AppError("Invalid code", Errcode.ErrcodeInvalidRequest.value, 401)


class RegisterHandler(RequestHandlerMixin, BaseRequestHandler):
    @RequestHandlerMixin.handle_request(RegisterSchema)
    def post(self):
        """
        ---
        tags: [Auth]
        summary: User registration
        description: Register a new user and return JWT token

        requestBody:
            description: Register data
            required: True
            content:
                application/json:
                    schema:
                        RegisterSchema

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                      type: object
                      properties:
                        token:
                            type: string

          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        user = AuthService.register(
            self.validated_data["email"], self.validated_data["username"], self.validated_data["password"]
        )
        if user:
            token = AuthService.generate_token(user)
            return {"token": token}
        else:
            raise AppError("User already exists", Errcode.ErrcodeUnauthorized.value, 400)


api_router.add("/api/auth/login", LoginHandler)
api_router.add("/api/auth/guest-token", GuestTokenHandler)
api_router.add("/api/auth/register", RegisterHandler)
