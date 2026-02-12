"""Unit tests for transcription. Mocked OpenAI; no network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models import STTRequest
from app.transcribe import (
    _decode_audio,
    _mock_response,
    transcribe,
)


def test_decode_audio_data_url() -> None:
    """Decode base64 from data URL."""
    b64 = "AAAA"  # valid base64 (decodes to 3 bytes)
    data_url = f"data:audio/mp3;base64,{b64}"
    data, fmt = _decode_audio(data_url)
    assert isinstance(data, bytes)
    assert fmt == "mp3"


def test_decode_audio_data_url_wav() -> None:
    """Data URL with audio/wav returns wav format."""
    data_url = "data:audio/wav;base64,AAAA"
    _, fmt = _decode_audio(data_url)
    assert fmt == "wav"


def test_decode_audio_invalid_data_url_raises() -> None:
    """Invalid data URL (no comma) raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="Invalid data URL"):
        _decode_audio("data:audio/mp3;base64")


def test_decode_audio_non_url_raises() -> None:
    """Non-URL audio_ref raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="data URL or HTTP"):
        _decode_audio("not-a-url")


@patch("app.transcribe.httpx.get")
def test_decode_audio_http_url(mock_get: MagicMock) -> None:
    """HTTP URL fetches and returns bytes."""
    mock_get.return_value = MagicMock(
        status_code=200,
        content=b"fake audio",
        headers={"content-type": "audio/mpeg"},
    )
    data, fmt = _decode_audio("https://example.com/audio.mp3")
    assert data == b"fake audio"
    assert fmt == "mp3"
    mock_get.assert_called_once()


def test_mock_response_validates() -> None:
    """Mock response has required fields and validates."""
    req = STTRequest(audio_ref="data:audio/mp3;base64,//uQx", language="en")
    r = _mock_response(req)
    assert r.x_contract_version == "1.0"
    assert r.request == req
    assert r.transcript == "[Mock transcript: audio received]"
    assert r.language == "en"
    assert r.confidence == 0.95
    assert r.error is None


@patch("app.transcribe._get_client", return_value=None)
def test_transcribe_no_client_returns_mock(get_client: MagicMock) -> None:
    """When OpenAI client is None (no API key), transcribe returns mock."""
    req = STTRequest(audio_ref="https://example.com/audio.mp3")
    r = transcribe(req)
    get_client.assert_called_once()
    assert r.transcript == "[Mock transcript: audio received]"
    assert r.error is None


@patch("app.transcribe._get_client")
def test_transcribe_decode_failure_returns_error(mock_get_client: MagicMock) -> None:
    """When audio decode fails, transcribe returns valid schema with error."""
    mock_get_client.return_value = MagicMock()
    req = STTRequest(audio_ref="not-a-valid-ref")
    r = transcribe(req)
    assert r.transcript == ""
    assert r.error is not None
    assert "data URL" in r.error or "HTTP" in r.error


@patch("app.transcribe._get_client")
def test_transcribe_api_failure_returns_error(mock_get_client: MagicMock) -> None:
    """When OpenAI API fails, transcribe returns valid schema with error."""
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = Exception("API rate limit")
    mock_get_client.return_value = mock_client

    req = STTRequest(audio_ref="data:audio/mp3;base64,AAAAAAAA")  # valid base64
    r = transcribe(req)
    assert r.transcript == ""
    assert r.error is not None
    assert "rate limit" in r.error or "API" in r.error


@patch("app.transcribe._get_client")
def test_transcribe_success_returns_transcript(mock_get_client: MagicMock) -> None:
    """Successful transcription returns transcript in contract format."""
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(
        text="Hello, I want to book a flight to Paris.",
        usage=MagicMock(seconds=3.2),
    )
    mock_get_client.return_value = mock_client

    req = STTRequest(audio_ref="data:audio/mp3;base64,AAAAAAAA", language="en")  # valid base64
    r = transcribe(req)
    assert r.transcript == "Hello, I want to book a flight to Paris."
    assert r.error is None
    assert r.duration_seconds == 3.2
    mock_client.audio.transcriptions.create.assert_called_once()
