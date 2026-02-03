from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Optional


app = FastAPI(title="mcp-travel-products", version="0.1.0")


class RetrieveProductCandidatesRequest(BaseModel):
    query: str = Field(min_length=1)
    destination: Optional[str] = None
    market: str = "BR"
    lang: Optional[str] = None
    limit: int = 8
    min_confidence: float = 0.0
    debug: bool = False


class ProductCandidate(BaseModel):
    product_id: str
    summary: str
    link: str
    merchant: str = ""
    primaryCategory: str = "other"
    categories: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    affiliatePriority: float = 0.0
    userValue: float = 0.0
    confidence: float = 0.0
    score: dict[str, Any] = Field(default_factory=dict)


class RetrieveProductCandidatesResponse(BaseModel):
    candidates: list[ProductCandidate] = Field(default_factory=list)
    debug: Optional[dict[str, Any]] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/retrieve_product_candidates", response_model=RetrieveProductCandidatesResponse)
def retrieve_product_candidates(req: RetrieveProductCandidatesRequest) -> RetrieveProductCandidatesResponse:
    dbg = {"note": "stub"} if req.debug else None
    return RetrieveProductCandidatesResponse(candidates=[], debug=dbg)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8020, reload=True)


if __name__ == "__main__":
    main()
