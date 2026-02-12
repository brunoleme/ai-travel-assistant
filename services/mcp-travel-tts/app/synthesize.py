"""Call OpenAI TTS API with text + voice settings; return audio_ref (data URL)."""

from __future__ import annotations

import base64
import os
from typing import Optional

from openai import OpenAI

from app.models import TTSRequest, SynthesizeResponse

# OpenAI TTS voices (contract-allowed)
TTS_VOICES = frozenset({"alloy", "echo", "fable", "onyx", "nova", "shimmer"})

# Map contract format to OpenAI response_format
TTS_FORMAT_MAP = {
    "mp3": "mp3",
    "opus": "opus",
    "aac": "aac",
    "wav": "wav",
    "pcm": "pcm",
}


def _get_client() -> OpenAI | None:
    """Return OpenAI client or None if no API key."""
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)


def _get_model() -> str:
    """TTS model from env (default gpt-4o-mini-tts)."""
    return os.environ.get("TTS_MODEL", "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"


def _get_default_voice() -> str:
    """Default voice from env (default alloy)."""
    v = (os.environ.get("TTS_VOICE") or "alloy").strip().lower()
    return v if v in TTS_VOICES else "alloy"


def _mock_response(req: TTSRequest) -> SynthesizeResponse:
    """Return mock audio_ref for scaffold / no API key (validates against contract)."""
    fmt = req.format or "mp3"
    # Minimal valid base64 audio placeholder (tiny mp3 header-like bytes)
    b64 = base64.b64encode(b"\x00\x00\x00").decode("ascii")
    audio_ref = f"data:audio/{fmt};base64,{b64}"
    return SynthesizeResponse(
        x_contract_version="1.0",
        request=req,
        audio_ref=audio_ref,
        format=fmt,
        duration_seconds=None,
        error=None,
        debug={"mock": True} if req.debug else None,
    )


def synthesize(req: TTSRequest) -> SynthesizeResponse:
    """
    Synthesize speech via OpenAI TTS API; return contract response.
    On failure, return valid schema with error set and empty audio_ref.
    """
    client = _get_client()
    if client is None:
        return _mock_response(req)

    model = _get_model()
    voice = (req.voice or _get_default_voice()).lower()
    if voice not in TTS_VOICES:
        voice = _get_default_voice()
    response_format = TTS_FORMAT_MAP.get(req.format or "mp3", "mp3")
    speed = req.speed if req.speed is not None else 1.0

    try:
        resp = client.audio.speech.create(
            model=model,
            voice=voice,
            input=req.text,
            response_format=response_format,
            speed=speed,
        )
    except Exception as e:
        # Contract requires audio_ref minLength 1; use placeholder on error
        placeholder = "data:audio/mp3;base64,YQ=="
        return SynthesizeResponse(
            x_contract_version="1.0",
            request=req,
            audio_ref=placeholder,
            format=req.format,
            duration_seconds=None,
            error=str(e),
            debug={"api_error": str(e)} if req.debug else None,
        )

    # Response is streaming bytes; read all (SDK may expose .content or .read())
    audio_bytes: bytes = b""
    if hasattr(resp, "content") and isinstance(getattr(resp, "content"), bytes):
        audio_bytes = resp.content
    elif hasattr(resp, "read") and callable(getattr(resp, "read")):
        data = resp.read()
        if isinstance(data, bytes):
            audio_bytes = data
    if not audio_bytes:
        placeholder = "data:audio/mp3;base64,YQ=="
        return SynthesizeResponse(
            x_contract_version="1.0",
            request=req,
            audio_ref=placeholder,
            format=req.format,
            duration_seconds=None,
            error="Empty audio response",
            debug={"model": model} if req.debug else None,
        )

    b64 = base64.b64encode(audio_bytes).decode("ascii")
    mime = f"audio/{response_format}"
    audio_ref = f"data:{mime};base64,{b64}"

    # OpenAI TTS does not return duration; leave None unless we compute from bytes
    duration_seconds: Optional[float] = None

    return SynthesizeResponse(
        x_contract_version="1.0",
        request=req,
        audio_ref=audio_ref,
        format=req.format or "mp3",
        duration_seconds=duration_seconds,
        error=None,
        debug={"model": model} if req.debug else None,
    )
