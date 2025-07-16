from core.errors.errcode import Errcode
from core.errors.notfound import NotFoundError
from core.errors.validate import ValidateError
from core.tts.tts import get_tts_voices, text2speech
from handlers.base_handler import BaseProtectedHandler
from handlers.router import api_router


class TTSHandler(BaseProtectedHandler):
    async def post(self):
        """
        ---
        tags:
          - TTS
        summary: Get tts audio with text
        description:
          Get tts audio with tts_type, tts_params(text/voice/rate/volume).
        parameters:
          - name: tts_type
            in: query
            required: true
            description: TTS type('edge_tts', other tts).
            type: string
          - name: tts_params
            in: query
            required: true
            description: TTS Params, for edge_tts(text/voice/rate/volume).
            type: object
            properties:
                text:
                  type: string
                  description: Text to speech.
                voice:
                  type: string
                  description: "Speech voice, default: 'zh-CN-XiaoyiNeural'."
                rate:
                  type: string
                  description: "Speech rate (range: -100% to +100%);"
                volume:
                  type: string
                  description: "Speech volume (range: -100% to +100%)."
        responses:
          200:
            description: "base64 encoded audio message, {'status': 0, 'data': base64str}"
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                data:
                  type: string
        """
        tts_type = self.req_dict.get("tts_type", "edge_tts")
        tts_params = self.req_dict.get("tts_params", {})

        try:
            res = await text2speech(tts_type, tts_params)
            self.write({"errcode": 0, "data": res})
        except ValidateError as e:
            self.set_status(400)
            self.write({"errcode": Errcode.ErrcodeInvalidRequest.value, "msg": str(e)})
        except NotFoundError as e:
            self.set_status(404)
            self.write({"errcode": Errcode.ErrcodeRequestNotFound.value, "msg": str(e)})
        except Exception as e:
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": str(e)})


class TTSVoicesHandler(BaseProtectedHandler):
    async def post(self):
        """
        ---
        tags:
          - TTS
        summary: Get tts voices with tts_type
        description:
          "Get tts voices with tts_type: 'edge_tts'."
        parameters:
          - name: tts_type
            in: query
            required: true
            description: TTS type('edge_tts', other tts).
            type: string
        responses:
          200:
            description: "voices of tts_type: {'status': 0, 'data': voices}, voices is a list"
            schema:
              type: object
              properties:
                errcode:
                  type: integer
                data:
                  type: array
                  items:
                    type: object
                    properties:
                      ShortName:
                        type: string
                        description: Voice shortname
                      Gender:
                        type: string
                        description: Voice with Gender
                      Locale:
                        type: string
                        description: Voice with Locale
                      SuggestedCodec:
                        type: string
                        description: Recommended SuggestedCodec
        """
        tts_type = self.req_dict.get("tts_type", "edge_tts")

        try:
            res = await get_tts_voices(tts_type)
            self.write({"errcode": 0, "data": res})
        except ValidateError as e:
            self.set_status(400)
            self.write({"errcode": Errcode.ErrcodeInvalidRequest.value, "msg": str(e)})
        except NotFoundError as e:
            self.set_status(404)
            self.write({"errcode": Errcode.ErrcodeRequestNotFound.value, "msg": str(e)})
        except Exception as e:
            self.set_status(500)
            self.write({"errcode": Errcode.ErrcodeInternalServerError.value, "msg": str(e)})


api_router.add("/api/tts/tts", TTSHandler)
api_router.add("/api/tts/voices", TTSVoicesHandler)
