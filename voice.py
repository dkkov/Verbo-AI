# -*- coding: utf-8 -*-
"""
voice.py — голос через Gemini: распознавание (STT) и озвучка (TTS).

Оба используют тот же ключ Gemini. Логика бота не дублируется: STT даёт текст,
который уходит в обычный generate_reply, а его ответ озвучивается TTS.
"""
import io
import wave

from google.genai import types as gt

from config import gemini_client, MODEL_MAIN, log
from llm import with_retry

# TTS-модель и голос. Голоса Gemini: Kore, Puck, Aoede, Charon, Fenrir и др.
TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_VOICE = "Kore"
TTS_RATE = 24000  # Gemini TTS отдаёт PCM 24кГц, 16-бит, моно


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Распознаёт речь из аудио. Возвращает чистый текст."""
    def _run():
        return gemini_client.models.generate_content(
            model=MODEL_MAIN,
            contents=[
                gt.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribe the speech in this audio in its original language. "
                "Return ONLY the transcribed text — no quotes, no explanations, "
                "no prefixes.",
            ],
            config=gt.GenerateContentConfig(temperature=0),
        )

    resp = with_retry(_run, what="gemini:stt")
    return (resp.text or "").strip()


def synthesize(text: str, voice: str = TTS_VOICE) -> bytes:
    """Озвучивает текст. Возвращает WAV-байты (готово для <audio>)."""
    def _run():
        return gemini_client.models.generate_content(
            model=TTS_MODEL,
            contents=text,
            config=gt.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=gt.SpeechConfig(
                    voice_config=gt.VoiceConfig(
                        prebuilt_voice_config=gt.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )

    resp = with_retry(_run, what="gemini:tts")
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    return _pcm_to_wav(pcm, TTS_RATE)


def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    """Заворачивает сырой PCM (16-бит моно) в WAV-контейнер."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()
