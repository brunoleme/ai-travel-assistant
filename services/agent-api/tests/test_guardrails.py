"""Guardrails validator tests (TDD)."""

from __future__ import annotations

from app.guardrails import validate_and_fix


def test_factual_without_citations_gets_rewritten() -> None:
    """Answer with factual heuristic and no citations -> rewritten to safe message."""
    response = {
        "session_id": "s1",
        "request_id": "r1",
        "answer_text": "You must visit at 8am. The rule requires advance booking.",
        "citations": [],
        "addon": None,
    }
    out = validate_and_fix(response, "when to go to Disney")
    assert out["answer_text"] == "Não tenho fontes suficientes para confirmar essas informações."
    assert out["citations"] == []


def test_product_addon_removed_when_not_requested() -> None:
    """Product suggested when user didn't request that bucket -> addon removed."""
    response = {
        "session_id": "s1",
        "request_id": "r1",
        "answer_text": "Best times are early morning.",
        "citations": ["https://example.com"],
        "addon": {
            "product_id": "prod_hotel_123",
            "summary": "Best hotel deals in Orlando",
            "link": "https://hotels.com",
            "merchant": "Hotels.com",
        },
    }
    out = validate_and_fix(response, "dicas para evitar filas na Disney")
    assert out["addon"] is None


def test_citations_present_guardrails_pass_unchanged() -> None:
    """When citations present, guardrails pass response unchanged."""
    response = {
        "session_id": "s1",
        "request_id": "r1",
        "answer_text": "You must visit at 8am. Rule requires advance booking.",
        "citations": ["https://example.com/tips"],
        "addon": None,
    }
    out = validate_and_fix(response, "dicas Disney")
    assert out["answer_text"] == response["answer_text"]
    assert out["citations"] == response["citations"]
    assert out["addon"] is None


