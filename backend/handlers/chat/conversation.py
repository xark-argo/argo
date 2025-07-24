from concurrent.futures import ThreadPoolExecutor

from tornado import gen
from tornado.concurrent import run_on_executor

from core.entities.user_entities import UserType
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin, allowed_user_types
from handlers.router import api_router
from handlers.wraps import validate_uuid_param
from schemas.conversation import (
    ConversationItemSchema,
    GetConversationQuerySchema,
    GetConversationsResponseSchema,
)
from schemas.schemas import BaseSuccessSchema
from services.bot.bot_service import BotService
from services.conversation.conversation_service import (
    ConversationService,
    MessageService,
)


@allowed_user_types(user_types=[UserType.USER, UserType.GUEST])
class ConversationsHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(GetConversationQuerySchema)
    def get(self):
        """
        ---
        tags: [Conversations]
        summary: Retrieve a list of conversations
        description: |
          This endpoint retrieves a list of conversations. The results can be filtered by \
          providing a `last_id` to paginate through the conversations.

          Guest Access: ✅ Allowed

        parameters:
          - name: last_id
            in: query
            required: false
            description: The ID of the last conversation from the previous page. Used for pagination.
            type: integer
          - name: limit
            in: query
            required: false
            description: The number of conversations to retrieve. Defaults to 10.
            type: integer

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        GetConversationsResponseSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        limit = self.validated_data["limit"]
        conversations, has_more = ConversationService.pagination_by_last_id(
            self.current_user.id, self.validated_data.get("last_id"), limit
        )

        bot_ids = list({conversation.bot_id for conversation in conversations})
        bots_info = BotService.get_bots_info(bot_ids)

        latest_answers = {conv.id: MessageService.get_latest_answer(conv.id) for conv in conversations}

        conversation_schema = GetConversationsResponseSchema(
            context={
                "bots_info": bots_info,
                "latest_answers": latest_answers,
            },
        )
        return conversation_schema.dump(
            {
                "has_more": has_more,
                "limit": limit,
                "data": conversations,
            }
        )

    @RequestHandlerMixin.handle_request()
    def post(self):
        """
        ---
        tags: [Conversations]
        summary: Create a new conversation
        description: |
          Creates a new conversation with the given web and user_id.

          Guest Access: ✅ Allowed

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        ConversationItemSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """
        conversation = ConversationService.create(self.current_user.id)
        return ConversationItemSchema().dump(conversation)


@allowed_user_types(user_types=[UserType.USER, UserType.GUEST])
class ConversationHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def delete(self, conversation_id):
        """
        ---
        tags:
          - Conversations
        summary: Delete an existing Conversation
        description: |
          Delete an existing Conversation

          Guest Access: ✅ Allowed

        produces:
          - application/json
        parameters:
          - name: conversation_id
            in: path
            required: true
            type: string

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        ConversationItemSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        ConversationService.delete(conversation_id)
        return BaseSuccessSchema().dumps({"msg": "Conversation deleted successfully"})


@allowed_user_types(user_types=[UserType.USER, UserType.GUEST])
class ConversationRenameHandler(BaseProtectedHandler):
    executor = ThreadPoolExecutor(max_workers=10)

    @run_on_executor
    def _background_task(self, conversation_id, name, auto_generate):
        conversation = ConversationService.rename(conversation_id, name, bool(auto_generate))
        return {
            "id": conversation.id,
            "bot_id": conversation.bot_id,
            "name": conversation.name,
        }

    @gen.coroutine
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def post(self, conversation_id):
        """
        ---
        tags: [Conversations]
        summary: Update the name of a conversation
        description: |
          This endpoint updates the name of a specific conversation. \
          You can also specify whether the name should be auto-generated.

          Guest Access: ✅ Allowed

        parameters:
          - name: conversation_id
            in: path
            required: true
            type: string
          - name: body
            in: body
            required: true
            schema:
              type: object
              properties:
                name:
                  type: string
                  description: The new name of the conversation.
                  example: "New Conversation Name"
                auto_generate:
                  type: boolean
                  description: Whether the name should be auto-generated.
                  example: false

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                      type: object
                      properties:
                        id:
                          type: string
                        bot_id:
                          type: string
                        name:
                          type: string
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """
        name = self.req_dict.get("name", "")
        auto_generate = self.req_dict.get("auto_generate", "False")

        yield self._background_task(conversation_id, name, auto_generate)


@allowed_user_types(user_types=[UserType.USER, UserType.GUEST])
class ClearMessagesHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def delete(self, conversation_id):
        """
        ---
        tags: [Conversations]
        summary: Clear all messages in a specific conversation
        description: |
          Clears all messages related to a specified bot in the conversation.

          Guest Access: ✅ Allowed

        parameters:
          - in: path
            name: conversation_id
            required: true
            type: string
            description: The unique identifier of the conversation.

        responses:
          200:
            description: Messages cleared successfully.
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

        ConversationService.clear_messages(conversation_id)
        return BaseSuccessSchema().dump({"msg": "Messages cleared successfully"})


class CreateBranchHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def post(self, conversation_id):
        """
        ---
        tags: [Conversations]
        summary: Create a branch from an existing conversation
        description: Creates a new conversation by copying messages from an \
        existing conversation starting from a specified message.

        parameters:
          - name: conversation_id
            in: path
            required: true
            type: string
          - name: body
            in: body
            required: true
            schema:
              type: object
              properties:
                message_id:
                  type: string
                  description: The message ID from which to create the branch.

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        ConversationItemSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        message_id = self.req_dict.get("message_id")

        if not conversation_id or not message_id:
            raise ValueError("Both conversation_id and message_id are required")

        new_conversation = ConversationService.create_branch(conversation_id, message_id)
        bots_info = BotService.get_bots_info([new_conversation.bot_id])
        latest_answers = {conv.id: MessageService.get_latest_answer(conv.id) for conv in [new_conversation]}

        conversation_schema = ConversationItemSchema(
            context={
                "bots_info": bots_info,
                "latest_answers": latest_answers,
            },
        )

        return conversation_schema.dump(new_conversation)


api_router.add("/api/conversations", ConversationsHandler)
api_router.add(r"/api/conversation/([0-9a-zA-Z-]+)", ConversationHandler)
api_router.add("/api/conversation/([0-9a-zA-Z-]+)/name", ConversationRenameHandler)
api_router.add("/api/conversation/([0-9a-zA-Z-]+)/messages", ClearMessagesHandler)
api_router.add("/api/conversation/([0-9a-zA-Z-]+)/branch", CreateBranchHandler)
