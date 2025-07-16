import base64
import logging

import edge_tts


async def text2speech(tts_type, tts_params):
    try:
        if tts_type == "edge_tts":
            text = tts_params.get("text", "")
            voice = tts_params.get("voice", "zh-CN-XiaoyiNeural")
            rate = tts_params.get("rate", "+0%")
            volume = tts_params.get("volume", "+100%")
            return await text2speech_edge_tts(text, voice, rate, volume)
        else:
            logging.error(f"text2speech get undefined tts_type: {tts_type}")
            return ""
    except Exception as e:
        logging.exception("text2speech error.")
        return ""


async def text2speech_edge_tts(text, voice="zh-CN-XiaoyiNeural", rate="+0%", volume="+100%"):
    if text == "":
        logging.error("text2speech_edge_tts with empty text")
        return

    try:
        audio_data = b""
        tts = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        base64_audio = base64.b64encode(audio_data).decode("utf-8")
        return base64_audio
    except Exception as e:
        logging.exception("text2speech_edge_tts error.")
    return ""


async def get_tts_voices(tts_type="edge_tts"):
    if tts_type == "edge_tts":
        return await get_edge_tts_voices()
    else:
        logging.error(f"get_tts_voices with undefined tts_type: {tts_type}")
        return []


async def get_edge_tts_voices():
    try:
        voices_list = await edge_tts.list_voices()
        return [
            {
                "ShortName": d.get("ShortName", ""),
                "Gender": d.get("Gender", ""),
                "Locale": d.get("Locale", ""),
                "SuggestedCodec": d.get("SuggestedCodec", ""),
            }
            for d in voices_list
        ]
    except Exception:
        logging.exception("get_edge_tts_voices error.")
    return []
