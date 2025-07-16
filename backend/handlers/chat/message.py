from core.errors.validate import ValidateError
from handlers.base_handler import BaseProtectedHandler, RequestHandlerMixin
from handlers.router import api_router
from handlers.wraps import validate_uuid_param
from schemas.message import (
    GetMessagesQuerySchema,
    GetMessagesResponseSchema,
    MessageItemSchema,
)
from schemas.schemas import BaseSuccessSchema
from services.conversation.conversation_service import MessageService


class MessagesHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(GetMessagesQuerySchema)
    def get(self):
        """
        ---
        tags: [Messages]
        summary: Retrieve a list of messages
        description:
          This endpoint retrieves a list of messages for a specific conversation.
          You can paginate the results using `first_id` and limit the number of messages returned using `limit`.

        parameters:
          - name: conversation_id
            in: query
            required: true
            description: The ID of the conversation to retrieve messages from.
            type: integer
          - name: first_id
            in: query
            required: false
            description: The ID of the first message from which to start retrieving. Used for pagination.
            type: integer
          - name: limit
            in: query
            required: false
            description: The number of messages to retrieve. Defaults to 20.
            type: integer

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        GetMessagesResponseSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        first_id = self.validated_data.get("first_id", None)
        conversation_id = self.validated_data.get("conversation_id", None)
        limit = self.validated_data["limit"]

        messages, has_more = MessageService.pagination_by_first_id(conversation_id, first_id, limit)
        return GetMessagesResponseSchema().dump(
            {
                "has_more": has_more,
                "limit": limit,
                "data": messages,
            }
        )


class MessageHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def post(self, message_id):
        """
        ---
        tags: [Messages]
        summary: Update a message
        description: Updates the query and answer fields of the message identified by the given message_id.

        parameters:
          - name: message_id
            in: path
            required: true
            type: string
          - name: body
            in: body
            required: true
            schema:
              type: object
              properties:
                query:
                  type: string
                  description: The updated query text.
                answer:
                  type: string
                  description: The updated answer text.
              required:
                - query
                - answer

        responses:
          200:
            description: Successful operation
            content:
                application/json:
                    schema:
                        MessageItemSchema
          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        query = self.req_dict.get("query", None)
        answer = self.req_dict.get("answer", None)
        if query is None or answer is None:
            raise ValidateError("Both query and answer are required")

        final_thought_id = self.req_dict.get("final_thought_id", None)

        message = MessageService.update(message_id, query, answer, final_thought_id)
        return MessageItemSchema().dumps(message)

    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def delete(self, message_id):
        """
        ---
        tags: [Messages]
        summary: Delete a message field or the entire message
        description: Deletes either the query, answer, or the entire message if both are deleted.

        parameters:
          - name: message_id
            in: path
            required: true
            type: string
          - name: body
            in: body
            required: true
            schema:
              type: object
              properties:
                delete_query:
                  type: boolean
                  description: Whether to delete query (optional).
                delete_answer:
                  type: boolean
                  description: Whether to delete answer (optional).

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

        delete_query = self.req_dict.get("delete_query", False)
        delete_answer = self.req_dict.get("delete_answer", False)

        if not delete_query and not delete_answer:
            raise ValidateError("At least one of delete_query or delete_answer must be true")

        if not message_id:
            raise ValidateError("Missing required field: message_id")

        MessageService.delete(message_id, delete_query, delete_answer)
        return BaseSuccessSchema().dumps({"msg": "Message deleted successfully"})


api_router.add("/api/messages", MessagesHandler)
api_router.add("/api/message/([0-9a-zA-Z-]+)", MessageHandler)
