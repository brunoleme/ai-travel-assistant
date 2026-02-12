"""Contract and request/response models for stt_transcript.schema.json."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class STTRequest(BaseModel):
    """Request payload nested inside the main request (matches contract)."""

    audio_ref: str = Field(
        min_length=1,
        description="Audio as data URL (data:audio/...;base64,...) or HTTP(S) URL",
    )
    language: Optional[str] = Field(
        default=None,
        description="Hint language (IETF tag e.g. en, pt-BR); null for auto-detect",
    )
    debug: bool = False


class TranscribePayload(BaseModel):
    """Top-level request payload matching contract schema."""

    x_contract_version: str = Field(default="1.0")
    request: STTRequest


class TranscribeResponse(BaseModel):
    """Response matching contract schema."""

    x_contract_version: str = "1.0"
    request: STTRequest
    transcript: str = Field(description="Primary transcript text")
    language: Optional[str] = Field(default=None, description="Detected language (IETF tag)")
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Transcription confidence"
    )
    duration_seconds: Optional[float] = Field(
        default=None, ge=0.0, description="Input audio duration in seconds"
    )
    error: Optional[str] = Field(default=None, description="Error message if transcription failed")
    debug: Optional[dict[str, Any]] = None
