"""Call OpenAI STT API with audio; map to contract."""

from __future__ import annotations

import base64
import io
import math
import os
from typing import Optional

import httpx
from openai import OpenAI

from app.models import STTRequest, TranscribeResponse


def _get_client() -> OpenAI | None:
    """Return OpenAI client or None if no API key."""
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)


def _get_model() -> str:
    """STT model from env (default gpt-4o-mini-transcribe)."""
    return (
        os.environ.get("STT_MODEL", "gpt-4o-mini-transcribe").strip()
        or "gpt-4o-mini-transcribe"
    )


def _decode_audio(audio_ref: str) -> tuple[bytes, str]:
    """
    Decode audio from data URL or fetch from HTTP URL.
    Returns (audio_bytes, format_hint). format_hint is extension for API (mp3, wav, etc.).
    """
    ref = audio_ref.strip()
    if ref.startswith("data:"):
        prefix, _, b64 = ref.partition(",")
        if not b64:
            raise ValueError("Invalid data URL: missing base64 payload")
        mime = ""
        for part in prefix.replace("data:", "").split(";"):
            if part.startswith("audio/"):
                mime = part
                break
        ext_map = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/m4a": "m4a",
            "audio/flac": "flac",
        }
        fmt = ext_map.get(mime, "mp3")
        data = base64.b64decode(b64)
        return data, fmt
    if ref.startswith("http://") or ref.startswith("https://"):
        resp = httpx.get(ref, timeout=30.0)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "") or ""
        ext_map = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/m4a": "m4a",
            "audio/flac": "flac",
        }
        fmt = "mp3"
        for mime, e in ext_map.items():
            if mime in content_type:
                fmt = e
                break
        return resp.content, fmt
    raise ValueError("audio_ref must be data URL or HTTP(S) URL")


def _mock_response(req: STTRequest) -> TranscribeResponse:
    """Return mock transcript for scaffold / no API key (validates against contract)."""
    return TranscribeResponse(
        x_contract_version="1.0",
        request=req,
        transcript="[Mock transcript: audio received]",
        language=req.language or "en",
        confidence=0.95,
        duration_seconds=None,
        error=None,
        debug={"mock": True} if req.debug else None,
    )


def transcribe(req: STTRequest) -> TranscribeResponse:
    """
    Transcribe audio via OpenAI STT API; return contract response.
    On failure, return valid schema with error set and empty transcript.
    """
    client = _get_client()
    if client is None:
        return _mock_response(req)

    try:
        audio_bytes, fmt = _decode_audio(req.audio_ref)
    except Exception as e:
        return TranscribeResponse(
            x_contract_version="1.0",
            request=req,
            transcript="",
            language=None,
            confidence=None,
            duration_seconds=None,
            error=str(e),
            debug={"decode_error": str(e)} if req.debug else None,
        )

    model = _get_model()
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = f"audio.{fmt}"

    try:
        resp = client.audio.transcriptions.create(
            file=file_obj,
            model=model,
            language=(req.language or None),
            response_format="json",
        )
    except Exception as e:
        return TranscribeResponse(
            x_contract_version="1.0",
            request=req,
            transcript="",
            language=None,
            confidence=None,
            duration_seconds=None,
            error=str(e),
            debug={"api_error": str(e)} if req.debug else None,
        )

    transcript_text = getattr(resp, "text", "") or ""
    duration_seconds: Optional[float] = None
    confidence: Optional[float] = None
    if hasattr(resp, "usage") and resp.usage is not None:
        usage = resp.usage
        if hasattr(usage, "seconds") and usage.seconds is not None:
            duration_seconds = float(usage.seconds)
    if hasattr(resp, "logprobs") and resp.logprobs and len(resp.logprobs) > 0:
        avg_logprob = sum(
            getattr(t, "logprob", 0) or 0 for t in resp.logprobs
        ) / len(resp.logprobs)
        confidence = min(1.0, max(0.0, math.exp(avg_logprob))) if avg_logprob else None

    return TranscribeResponse(
        x_contract_version="1.0",
        request=req,
        transcript=transcript_text,
        language=req.language or None,
        confidence=confidence,
        duration_seconds=duration_seconds,
        error=None,
        debug={"model": model} if req.debug else None,
    )
