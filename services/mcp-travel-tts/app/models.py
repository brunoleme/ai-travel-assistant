"""Contract and request/response models for tts_audio.schema.json."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TTSFormat = Literal["mp3", "opus", "aac", "wav", "pcm"]
TTSVoice = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


class TTSRequest(BaseModel):
    """Request payload nested inside the main request (matches contract)."""

    text: str = Field(min_length=1, description="Text to synthesize")
    voice: Optional[str] = Field(
        default=None,
        description="Voice ID (e.g. alloy, echo, fable, onyx, nova, shimmer); null for default",
    )
    language: Optional[str] = Field(
        default=None,
        description="IETF tag e.g. en, pt-BR",
    )
    speed: Optional[float] = Field(
        default=None,
        ge=0.25,
        le=4.0,
        description="Speech speed (1.0 = normal)",
    )
    format: Optional[TTSFormat] = Field(
        default=None,
        description="Output format; null for default (mp3)",
    )
    debug: bool = False


class SynthesizePayload(BaseModel):
    """Top-level request payload matching contract schema."""

    x_contract_version: str = Field(default="1.0")
    request: TTSRequest


class SynthesizeResponse(BaseModel):
    """Response matching contract schema."""

    x_contract_version: str = "1.0"
    request: TTSRequest
    audio_ref: str = Field(
        min_length=1,
        description="Audio as data URL (data:audio/...;base64,...) or HTTP(S) URL",
    )
    format: Optional[TTSFormat] = Field(
        default=None,
        description="Actual output format",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Synthesized audio duration in seconds",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if synthesis failed",
    )
    debug: Optional[dict[str, Any]] = None
