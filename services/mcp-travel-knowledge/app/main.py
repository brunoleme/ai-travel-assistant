from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Optional


app = FastAPI(title="mcp-travel-knowledge", version="0.1.0")


class RetrieveTravelEvidenceRequest(BaseModel):
    user_query: str = Field(min_length=1)
    destination: Optional[str] = None
    lang: Optional[str] = None
    debug: bool = False
    strategy_params: dict[str, Any] = Field(default_factory=dict)


class TravelEvidenceCard(BaseModel):
    card_id: str
    summary: str
    signals: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    primaryCategory: str = "other"
    confidence: float = 0.0
    source_url: str = ""
    videoUploadDate: Optional[str] = None
    score: dict[str, Any] = Field(default_factory=dict)
    seen_in_queries: list[str] = Field(default_factory=list)


class RetrieveTravelEvidenceResponse(BaseModel):
    expanded_queries: list[str] = Field(default_factory=list)
    evidence: list[TravelEvidenceCard] = Field(default_factory=list)
    debug: Optional[dict[str, Any]] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/retrieve_travel_evidence", response_model=RetrieveTravelEvidenceResponse)
def retrieve_travel_evidence(req: RetrieveTravelEvidenceRequest) -> RetrieveTravelEvidenceResponse:
    # Phase 1 stub: returns empty evidence but valid shape.
    dbg = {"note": "stub"} if req.debug else None
    return RetrieveTravelEvidenceResponse(expanded_queries=[], evidence=[], debug=dbg)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8010, reload=True)


if __name__ == "__main__":
    main()
