from enum import Enum


class Errcode(Enum):
    ErrcodeSuccess = -1
    ErrcodeInternalServerError = -2
    ErrcodeParseFailed = -100
    ErrcodeDuplicateOperate = -101
    ErrcodeRequestNotFound = -102

    ErrCreateCollectionFail = -136
    ErrDropCollectionFail = -137
    ErrCreatePartitionFail = -138
    ErrShowDocumentFail = -139
    ErrBindSpaceFail = -140
    ErrUnBindSpaceFail = -141
    ErrRemoveDocumentFail = -143
    ErrFileUploadFail = -153
    ErrFileDeleteFail = -154
    ErrBotInstallFail = -155

    ErrRagFail = -204

    # Chat
    ErrcodeOllamaInvokeError = -300
    ErrcodeOllamaModelNotFound = -301
    ErrcodeBotModelNotConfigured = -302
    ErrcodeOllamaConnectionError = -303
    ErrcodeOllamaMemoryError = -304

    ErrcodeUnauthorized = -88888
    ErrcodeInvalidRequest = -99999
