import os
from pathlib import Path

from configs.env import ARGO_STORAGE_PATH_TEMP_BOT
from core.entities.bot_entities import ProviderStatus
from core.errors.errcode import Errcode
from core.errors.notfound import NotFoundError
from core.errors.validate import ValidateError
from handlers.base_handler import (
    AppError,
    BaseProtectedHandler,
    BaseRequestHandler,
    RequestHandlerMixin,
)
from handlers.router import api_router
from handlers.wraps import validate_uuid_param
from models.bot import BotStatus, get_bot, set_bot_status
from models.document import DOCUMENTSTATUS
from models.model_manager import DownloadStatus
from schemas.bot import (
    BotModelConfigSchema,
    BotSchema,
    CreateBotSchema,
    DeleteBotSchema,
    ImportBotsSchema,
    ListBotSchema,
    bot_schema,
)
from services.bot.bot_service import BotService
from services.bot.import_bot import ImportBotService


class CreateBotHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(CreateBotSchema)
    def post(self):
        """
        ---
        tags: [Bot]
        summary: Create a bot
        description: Create a new bot

        requestBody:
            description: New bot data
            required: True
            content:
                application/json:
                    schema:
                        CreateBotSchema

        responses:
            200:
                description: Success payload containing newly created bot information
                content:
                    application/json:
                        schema:
                            BotSchema

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema

        """

        bot = BotService.create_bot(
            self.current_user,
            self.validated_data["space_id"],
            self.validated_data["name"],
            self.validated_data["description"],
            self.validated_data["icon"],
            self.validated_data["category"],
            self.validated_data.get("background_img"),
        )
        return bot_schema.dump(bot)


class GetBotHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def get(self, bot_id):
        """
        ---
        tags: [Bot]
        summary: Get bot details
        description: Get the bot and model config

        parameters:
        - name: bot_id
          in: path
          required: true
          type: string

        responses:
            200:
                description: Success payload containing newly created bot information
                content:
                    application/json:
                        schema:
                            BotModelConfigSchema
        """

        bot, model_config = BotService.get_bot_details(bot_id)
        bot_model_config_schema = BotModelConfigSchema(
            context={"model_config": model_config.to_dict()},
        )
        return bot_model_config_schema.dump(bot)


class ListBotsHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(ListBotSchema)
    def post(self):
        """
        ---
        tags: [Bot]
        summary: List all Bots
        description: Retrieve a list of all Bots

        requestBody:
            description: New bot data
            required: True
            content:
                application/json:
                    schema:
                        ListBotSchema

        responses:
            200:
                description: Success payload containing newly created bot information
                content:
                    application/json:
                        schema:
                            BotSchema

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema

        """

        bots = BotService.list_bots(self.validated_data["space_id"])
        bot_info_list = []
        for bot in bots:
            bot_detail = BotService.get_bot_detail(bot_id=bot.id)
            chat_model_flag = bot_detail.get("chat_model_info", {}).get("download_status", "")
            chat_model_provider_status = bot_detail.get("chat_model_info", {}).get("provider_status", "")

            embed_model_flag_list = [
                each.get("download_status", "") for each in bot_detail.get("embedding_model_info_list", [])
            ]
            knowledge_flag_list = [
                each.get("knowledge_status", "") for each in bot_detail.get("knowledge_info_list", [])
            ]

            if not bot_detail.get("chat_model_info", {}).get("model_name", ""):
                set_bot_status(bot_id=bot.id, status=BotStatus.BOT_TO_BE_EDITED.value)
            elif chat_model_provider_status == ProviderStatus.NOT_INIT.value:
                set_bot_status(bot_id=bot.id, status=BotStatus.BOT_UNINSTALL.value)
            elif (
                chat_model_flag == DownloadStatus.ALL_COMPLETE.value
                and all(each == DownloadStatus.ALL_COMPLETE.value for each in embed_model_flag_list)
                and all(each == DOCUMENTSTATUS.FINISH.value for each in knowledge_flag_list)
            ):
                set_bot_status(bot_id=bot.id, status=BotStatus.BOT_NORMAL.value)
            elif (
                chat_model_flag
                in [
                    DownloadStatus.DOWNLOAD_FAILED.value,
                    DownloadStatus.CONVERT_FAILED.value,
                    DownloadStatus.IMPORT_FAILED,
                    DownloadStatus.NOT_AVAILABLE.value,
                ]
                or any(
                    each
                    in [
                        DownloadStatus.DOWNLOAD_FAILED.value,
                        DownloadStatus.CONVERT_FAILED.value,
                        DownloadStatus.IMPORT_FAILED,
                        DownloadStatus.NOT_AVAILABLE.value,
                    ]
                    for each in embed_model_flag_list
                )
                or any(each == DOCUMENTSTATUS.FAIL.value for each in knowledge_flag_list)
            ):
                set_bot_status(bot_id=bot.id, status=BotStatus.BOT_FAIL.value)
            elif (
                chat_model_flag in [DownloadStatus.DELETE.value, DownloadStatus.INCOMPATIBLE.value]
                or any(each == DownloadStatus.DELETE.value for each in embed_model_flag_list)
                or any(each == DOCUMENTSTATUS.READY.value for each in knowledge_flag_list)
            ):
                set_bot_status(bot_id=bot.id, status=BotStatus.BOT_UNINSTALL.value)
            else:
                set_bot_status(bot_id=bot.id, status=BotStatus.BOT_INSTALLING.value)

            bot = get_bot(bot.id)
            bot_info_list.append(bot_schema.dump(bot))

        return {"bots": bot_info_list}


class UpdateBotHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(BotSchema)
    def post(self):
        """
        ---
        tags: [Bot]
        summary: Update an existing Bot
        description: Update the details of an existing Bot

        requestBody:
            description: Update bot data
            required: True
            content:
                application/json:
                    schema:
                        BotSchema

        responses:
            200:
                description: Success payload containing newly Updated bot information
                content:
                    application/json:
                        schema:
                            BotSchema

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema

        """

        bot = BotService.update_bot(
            self.validated_data["id"],
            self.validated_data["name"],
            self.validated_data["description"],
            self.validated_data["icon"],
            self.validated_data.get("background_img"),
        )
        return bot_schema.dump(bot)


class DeleteBotHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request(DeleteBotSchema)
    def post(self):
        """
        ---
        tags: [Bot]
        summary: Delete an existing Bot
        description: Delete the details of an existing Bot

        requestBody:
            description: Delete bot data
            required: True
            content:
                application/json:
                    schema:
                        DeleteBotSchema

        responses:
            200:
                description: Bot deleted successfully
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

        BotService.delete_bot(self.validated_data["space_id"], self.validated_data["bot_id"])
        return {"msg": "Bot deleted successfully"}


class ExportBotHandler(RequestHandlerMixin, BaseRequestHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def get(self, bot_id):
        """
        ---
        tags: [Bot]
        summary: Export a Bot Configuration
        description: Exports the configuration file of a specified bot by its ID.

        parameters:
          - in: path
            name: bot_id
            required: true
            description: The ID of the bot to export.
            schema:
              type: string

        responses:
            200:
                description: The bot configuration file is successfully exported.
                headers:
                  Content-Disposition:
                    description: Indicates that the response is an attachment with the file name.
                    type: string
                content:
                  application/octet-stream:
                    schema:
                      type: string
                      format: binary

            400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/octet-stream:
                        schema:
                            BaseErrorSchema

        """

        export_file, file_name = BotService.export_bot(bot_id)
        if not os.path.exists(export_file):
            raise NotFoundError("File not found")

        self.set_header("Content-Type", "application/octet-stream; charset=utf-8")
        self.set_header("Content-Disposition", f'attachment; filename="{file_name}"')
        with open(export_file, "rb") as f:
            while chunk := f.read(4096):
                self.write(chunk)
        self.finish()


class ImportBotHandler(BaseProtectedHandler):
    @RequestHandlerMixin.handle_request()
    def post(self):
        """
        ---
        tags: [Bot]
        summary: Import Bot(s)
        description: Upload a .zip/.yaml/.png file to import one or more bots.

        requestBody:
          required: true
          content:
            multipart/form-data:
              schema:
                type: object
                required:
                  - space_id
                  - files
                properties:
                  space_id:
                    type: string
                    description: ID of the space to which the bot belongs
                  files:
                    type: array
                    items:
                      type: string
                      format: binary
                    description: List of bot configuration files (.zip, .yaml, .png)

        responses:
          200:
            description: Successfully imported bot(s)
            content:
              application/json:
                schema:
                  ImportBotsSchema

          400:
                description: Bad request; Check `errors` for any validation errors
                content:
                    application/json:
                        schema:
                            BaseErrorSchema
        """

        files = self.request.files.get("files", [])
        if len(files) == 0:
            raise AppError("bot config empty", Errcode.ErrcodeInvalidRequest.value, 400)

        space_id = self.get_argument("space_id", "")

        bots = []
        for file_meta in files:
            file_content = file_meta["body"]
            file_name = file_meta["filename"]

            tmp_file_path = Path(ARGO_STORAGE_PATH_TEMP_BOT) / file_name
            tmp_file_path.write_bytes(file_content)

            tmp_file_path = str(tmp_file_path)
            if tmp_file_path.endswith(".zip"):
                bot = BotService.import_bot(space_id, self.current_user.id, tmp_file_path)
            elif tmp_file_path.endswith(".png"):
                bot = BotService.import_png_bot(space_id, self.current_user.id, tmp_file_path)
            elif tmp_file_path.endswith(".yaml") or tmp_file_path.endswith(".yml"):
                bot = ImportBotService.import_bot_from_yaml(space_id, self.current_user.id, tmp_file_path)
            else:
                raise ValidateError("Invalid Bot file")

            bots.append(bot)

        return ImportBotsSchema().dump({"bots": bots})


class ShareBotHandler(BaseProtectedHandler):
    @validate_uuid_param(0)
    @RequestHandlerMixin.handle_request()
    def get(self, bot_id):
        """
        ---
        tags: [Bot]
        summary: Share a Bot
        description: Share a Bot by its ID and return its public details.

        parameters:
          - in: path
            name: bot_id
            required: true
            schema:
              type: string
            description: The ID of the Bot to share.

        responses:
          200:
            description: Bot shared successfully
            content:
              application/json:
                schema:
                  BotSchema

          400:
            description: Bad request; Check `errors` for any validation errors
            content:
                application/json:
                    schema:
                        BaseErrorSchema
        """

        bot_details = BotService.share_bot(bot_id, user_id=self.current_user.id)
        return bot_details


api_router.add("/api/bot/create", CreateBotHandler)
api_router.add("/api/bot/([^/]+)/get", GetBotHandler)
api_router.add("/api/bot/list", ListBotsHandler)
api_router.add("/api/bot/update", UpdateBotHandler)
api_router.add("/api/bot/delete", DeleteBotHandler)
api_router.add("/api/bot/([^/]+)/export", ExportBotHandler)
api_router.add("/api/bot/import", ImportBotHandler)
api_router.add("/api/bot/([^/]+)/share", ShareBotHandler)
