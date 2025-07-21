from core.entities.user_entities import UserType
from core.i18n.translation import translation_loader
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin, allowed_user_types
from handlers.router import api_router
from handlers.wraps import validate_uuid_param
from models.conversation import get_message
from schemas.chat import GetPromptMessagesResponseSchema, SayChatSchema, StopChatSchema
from schemas.schemas import BaseSuccessSchema
from services.chat.chat_service import ChatService


@allowed_user_types(user_types=[UserType.USER, UserType.GUEST])
class SayChatHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(SayChatSchema)
    async def post(self):
        """
        ---
        tags: [Chat]
        summary: Send a chat message
        description: |
          Send a message to the bot for processing in a chat context.

          Guest Access: ✅ Allowed

        requestBody:
            description: Say chat data
            required: True
            content:
                application/json:
                    schema:
                        SayChatSchema


        responses:
          200:
            description: stream event
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        return ChatService.say(self.current_user.id, self.validated_data)


@allowed_user_types(user_types=[UserType.USER, UserType.GUEST])
class StopChatMessageHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(StopChatSchema)
    def post(self):
        """
        ---
        tags: [Chat]
        summary: Stop a chat message
        description: |
          Stops a specific chat message based on task_id and bot_id

          Guest Access: ✅ Allowed

        requestBody:
            description: Say chat data
            required: True
            content:
                application/json:
                    schema:
                        StopChatSchema

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        BaseSuccessSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        ChatService.stop_message(
            self.current_user.id,
            self.validated_data["bot_id"],
            self.validated_data["task_id"],
            self.validated_data["message_id"],
        )
        return BaseSuccessSchema().dumps({"msg": "success"})


class GetChatMessageHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def get(self, message_id):
        """
        ---
        tags: [Chat]
        summary: Get chat message detail
        description: Retrieve details of the specified chat message.

        parameters:
        - name: message_id
          in: path
          required: true
          type: string

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        GetPromptMessagesSuccessSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        message = get_message(message_id)
        if not message:
            self.write(GetPromptMessagesResponseSchema().dump({"data": {}}))
            return

        if message.agent_based:
            prompt_messages = [
                {
                    "role": "",
                    "text": translation_loader.translation.t("chat.agent_mode_prompt_log_hint"),
                }
            ]
        else:
            prompt_messages = message.message

        return GetPromptMessagesResponseSchema().dump({"data": {"prompt_messages": prompt_messages}})


api_router.add("/api/chat/say", SayChatHandler)
api_router.add("/api/chat/message/stop", StopChatMessageHandler)
api_router.add("/api/chat/message/([0-9a-zA-Z-]+)/get", GetChatMessageHandler)
