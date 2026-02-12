"""Unit tests for synthesis. Mocked OpenAI; no network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models import TTSRequest
from app.synthesize import (
    _mock_response,
    synthesize,
)


def test_mock_response_validates() -> None:
    """Mock response has required fields and validates."""
    req = TTSRequest(text="Hello, world.", voice="alloy")
    r = _mock_response(req)
    assert r.x_contract_version == "1.0"
    assert r.request == req
    assert r.audio_ref.startswith("data:audio/")
    assert "base64," in r.audio_ref
    assert r.error is None


@patch("app.synthesize._get_client", return_value=None)
def test_synthesize_no_client_returns_mock(get_client: MagicMock) -> None:
    """When OpenAI client is None (no API key), synthesize returns mock."""
    req = TTSRequest(text="Hello.")
    r = synthesize(req)
    get_client.assert_called_once()
    assert r.audio_ref.startswith("data:audio/")
    assert r.error is None


@patch("app.synthesize._get_client")
def test_synthesize_api_failure_returns_error(mock_get_client: MagicMock) -> None:
    """When OpenAI API fails, synthesize returns valid schema with error."""
    mock_client = MagicMock()
    mock_client.audio.speech.create.side_effect = Exception("API rate limit")
    mock_get_client.return_value = mock_client

    req = TTSRequest(text="Hello, world.")
    r = synthesize(req)
    assert r.error is not None
    assert "rate limit" in r.error or "API" in r.error
    # Contract requires audio_ref minLength 1
    assert len(r.audio_ref) >= 1


@patch("app.synthesize._get_client")
def test_synthesize_success_returns_audio_ref(mock_get_client: MagicMock) -> None:
    """Successful synthesis returns audio_ref in contract format (data URL)."""
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = MagicMock(
        content=b"fake_audio_bytes"
    )
    mock_get_client.return_value = mock_client

    req = TTSRequest(text="Welcome to Tokyo.", voice="nova", format="mp3")
    r = synthesize(req)
    assert r.audio_ref.startswith("data:audio/")
    assert "base64," in r.audio_ref
    assert r.error is None
    mock_client.audio.speech.create.assert_called_once()
