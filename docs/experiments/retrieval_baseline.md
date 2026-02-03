# Retrieval Baseline (Experiment → Production Reference)

This document describes the current retrieval approach in the experiments, as an algorithmic reference.
Production MCP implementations can start simple and grow toward this.

---

## Travel Evidence Retrieval (RecommendationCard)

### Inputs
- user_query: string
- destination: optional string (used mainly for planning context; filtering optional)
- lang: optional string
- per_query_limit: int (e.g., 6)
- cap_queries: int (e.g., 8)

### Step 1) Query expansion (LLM)
Goal: generate up to N expansions in the **same language** as the user query, each targeting a different angle.

Output:
- expanded_queries: list[str] (e.g., 4–6 strings)

### Step 2) Per-query vector retrieval (Weaviate)
For each query in:
- [original_query] + expanded_queries (capped)
Run near_text retrieval:
- limit = per_query_limit
- return properties needed for the EvidenceItem contract mapping
- request distance metadata when available

Output:
- per_query_hits: dict[query_string] -> list[RetrievedCard]

### Step 3) Quota then merge (dedupe)
Quota:
- keep top `k_original` results from the original query
- keep top `k_expansion` results from each expansion query
Then merge by UUID:
- dedupe by uuid
- keep the “best” instance per uuid (lowest distance)
- track where each uuid appeared:
  - seen_in_queries: [query strings]

Output:
- consolidated_candidates: list[Candidate]

Suggested defaults:
- k_original = 2
- k_expansion = 2
- max_candidates_after_merge = 30–40

### Step 4) Freshness penalty (optional)
If you have `videoUploadDate`, compute a small penalty for older content.

Suggested function:
- half_life_days = 180
- max_penalty = 0.20
Penalty gets added to distance-like score:
- adjusted_score = distance + freshness_penalty

Output:
- candidates_scored sorted by adjusted_score asc

### Step 5) Light rerank (LLM)
Provide a compact payload (summary + signals + source + dates + adjusted_score as weak hint).
Ask for:
- ranking list with short reasons
Return:
- final reranked list of top N (e.g., 10)

### Step 6) Contract mapping
Map final docs into `contracts/travel_evidence.schema.json` fields:
- card_id: use Weaviate UUID (string)
- summary: from card.summary
- signals: from card.signals
- places: from card.places
- categories: from card.categories
- primary_category: from card.primaryCategory
- confidence: from card.confidence (0..1)
- source_url: from card.timestampUrl
- video_upload_date: from card.videoUploadDate (optional)
- score: include distance + freshness_penalty + adjusted if available
- seen_in_queries: from merge stage
- rerank: rank + reason if rerank used

---

## Product Candidates Retrieval (ProductCard)

Very similar structure:
- retrieval from ProductCard
- optional LLM light rerank
- conservative gating (only output candidates; the agent runtime decides if it shows an addon)

Mapping to `contracts/product_candidates.schema.json`:
- product_id: UUID
- summary, merchant, link, categories, primary_category, triggers, constraints
- affiliate_priority, user_value, confidence
- score: include distance/rank if available

---

## Operational Constraints
- Unit tests must not call Weaviate or OpenAI directly.
- External calls go behind adapters and are mocked in tests.
- Use deterministic fixtures to validate contract output.
