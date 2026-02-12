SHELL := /bin/bash

# ---- Config ----
PY := uv run
UV := uv

# Services
AGENT_DIR := services/agent-api
KNOW_DIR  := services/mcp-travel-knowledge
PROD_DIR  := services/mcp-travel-products
GRAPH_DIR := services/mcp-travel-graph
VISION_DIR := services/mcp-travel-vision
STT_DIR   := services/mcp-travel-stt
TTS_DIR   := services/mcp-travel-tts
ING_DIR   := services/ingestion
TF_DIR    := infra/terraform

# ---- Help ----
.PHONY: help
help:
	@echo ""
	@echo "Targets:"
	@echo "  make bootstrap                 - Sync deps (per service)"
	@echo "  make fmt                        - Format all python services"
	@echo "  make lint                       - Lint all python services"
	@echo "  make test                       - Run unit tests for all services"
	@echo "  make test-agent | test-knowledge | test-products | test-graph | test-vision | test-stt | test-tts | test-ingestion"
	@echo "  make run-agent                   - Run FastAPI agent runtime"
	@echo "  make run-knowledge               - Run MCP travel-knowledge server"
	@echo "  make run-products                - Run MCP travel-products server"
	@echo "  make run-graph                   - Run MCP travel-graph server"
	@echo "  make run-vision                 - Run MCP travel-vision server"
	@echo "  make run-stt | run-tts         - Run MCP travel-stt / travel-tts server"
	@echo "  make eval                        - Run eval harness, write to data/eval/run.jsonl"
	@echo "  make eval-vision                 - Run vision eval (15 queries), write to data/eval/run_vision.jsonl"
	@echo "  make run-ingestion               - Run ingestion worker (local mode)"
	@echo "  make send-graph URL=... DESTINATION_HINT=...  - Enqueue one youtube_kg (Neo4j) job"
	@echo "  make send-playlist URL=... DESTINATION=... PLAYLIST_NAME=...  - Enqueue playlist (Weaviate)"
	@echo "  make tf-fmt | tf-validate        - Terraform formatting and validation"
	@echo ""

# ---- Bootstrap ----
.PHONY: bootstrap sync-agent sync-knowledge sync-products sync-graph sync-vision sync-stt sync-tts sync-ingestion
bootstrap: sync-agent sync-knowledge sync-products sync-graph sync-vision sync-stt sync-tts sync-ingestion

sync-agent:
	@echo "==> Sync $(AGENT_DIR) (with dev extras)"
	@cd $(AGENT_DIR) && $(UV) sync --extra dev

sync-knowledge:
	@echo "==> Sync $(KNOW_DIR) (with dev extras)"
	@cd $(KNOW_DIR) && $(UV) sync --extra dev

sync-products:
	@echo "==> Sync $(PROD_DIR) (with dev extras)"
	@cd $(PROD_DIR) && $(UV) sync --extra dev

sync-graph:
	@echo "==> Sync $(GRAPH_DIR) (with dev extras)"
	@cd $(GRAPH_DIR) && $(UV) sync --extra dev

sync-vision:
	@echo "==> Sync $(VISION_DIR) (with dev extras)"
	@cd $(VISION_DIR) && $(UV) sync --extra dev

sync-stt:
	@echo "==> Sync $(STT_DIR) (with dev extras)"
	@cd $(STT_DIR) && $(UV) sync --extra dev

sync-tts:
	@echo "==> Sync $(TTS_DIR) (with dev extras)"
	@cd $(TTS_DIR) && $(UV) sync --extra dev

sync-ingestion:
	@echo "==> Sync $(ING_DIR) (with dev extras)"
	@cd $(ING_DIR) && $(UV) sync --extra dev

# ---- Quality ----
.PHONY: fmt lint test
fmt: bootstrap
	@cd $(AGENT_DIR) && $(PY) ruff format .
	@cd $(KNOW_DIR)  && $(PY) ruff format .
	@cd $(PROD_DIR)  && $(PY) ruff format .
	@cd $(GRAPH_DIR) && $(PY) ruff format .
	@cd $(VISION_DIR) && $(PY) ruff format .
	@cd $(STT_DIR)   && $(PY) ruff format .
	@cd $(TTS_DIR)   && $(PY) ruff format .
	@cd $(ING_DIR)   && $(PY) ruff format .

lint: bootstrap
	@cd $(AGENT_DIR) && $(PY) ruff check .
	@cd $(KNOW_DIR)  && $(PY) ruff check .
	@cd $(PROD_DIR)  && $(PY) ruff check .
	@cd $(GRAPH_DIR) && $(PY) ruff check .
	@cd $(VISION_DIR) && $(PY) ruff check .
	@cd $(STT_DIR)   && $(PY) ruff check .
	@cd $(TTS_DIR)   && $(PY) ruff check .
	@cd $(ING_DIR)   && $(PY) ruff check .

test: test-agent test-knowledge test-products test-graph test-vision test-stt test-tts test-ingestion

test-agent: sync-agent
	@cd $(AGENT_DIR) && $(PY) python -m pytest -q

test-knowledge: sync-knowledge
	@cd $(KNOW_DIR) && $(PY) python -m pytest -q

test-products: sync-products
	@cd $(PROD_DIR) && $(PY) python -m pytest -q

test-graph: sync-graph
	@cd $(GRAPH_DIR) && $(PY) python -m pytest -q

test-vision: sync-vision
	@cd $(VISION_DIR) && $(PY) python -m pytest -q

test-stt: sync-stt
	@cd $(STT_DIR) && $(PY) python -m pytest -q

test-tts: sync-tts
	@cd $(TTS_DIR) && $(PY) python -m pytest -q

test-ingestion: sync-ingestion
	@cd $(ING_DIR) && $(PY) python -m pytest -q

# ---- Run (local dev) ----
# Load configs/.env so WEAVIATE_* etc. are set (run from repo root)
ENV_FILE := configs/.env

.PHONY: run-agent run-knowledge run-products run-graph run-vision run-stt run-tts run-ingestion
run-agent: sync-agent
	@cd $(AGENT_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8000

run-knowledge: sync-knowledge
	@cd $(KNOW_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8010

run-products: sync-products
	@cd $(PROD_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8020

run-graph: sync-graph
	@cd $(GRAPH_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8031

run-vision: sync-vision
	@cd $(VISION_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8032

run-stt: sync-stt
	@cd $(STT_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8033

run-tts: sync-tts
	@cd $(TTS_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8034

run-ingestion: sync-ingestion
	@cd $(ING_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) python -m app.main

# Send one graph ingestion (youtube_kg) for a single video. Example: make send-graph URL="https://www.youtube.com/watch?v=VID" DESTINATION_HINT="Orlando"
.PHONY: send-graph
send-graph: sync-ingestion
	@set -a && . $(ENV_FILE) && set +a && cd $(ING_DIR) && $(PY) python ../../scripts/send_graph_ingestion.py "$(URL)" --destination-hint "$(DESTINATION_HINT)"

# Send playlist ingestion (one message per video). Example: make send-playlist URL="https://www.youtube.com/playlist?list=..." DESTINATION="Maldivas" PLAYLIST_NAME="My Playlist"
.PHONY: send-playlist
send-playlist: sync-ingestion
	@set -a && . $(ENV_FILE) && set +a && cd $(ING_DIR) && $(PY) python ../../scripts/send_playlist_ingestion.py "$(URL)" --destination "$(DESTINATION)" --playlist-name "$(PLAYLIST_NAME)"

.PHONY: eval eval-vision
eval: sync-agent
	@cd $(AGENT_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) python -m app.eval_runner --out ../../data/eval/run.jsonl

# Vision eval: prepare 15 vision queries, run eval, write run_vision.jsonl
eval-vision: sync-agent
	@cd $(AGENT_DIR) && $(PY) python ../../scripts/prepare_vision_eval_queries.py --out data/eval/vision_queries.json
	@cd $(AGENT_DIR) && set -a && . ../../$(ENV_FILE) && set +a && \
		TEST_QUERIES_FILE=data/eval/vision_queries.json $(PY) python -m app.eval_runner --out ../../data/eval/run_vision.jsonl

# ---- Terraform ----
.PHONY: tf-fmt tf-validate tf-init-backend tf-plan tf-apply
tf-fmt:
	@cd $(TF_DIR) && terraform fmt -recursive

tf-validate:
	@cd $(TF_DIR) && terraform validate

# Initialize Terraform with S3 backend (bucket/region from .env).
tf-init-backend:
	@cd $(TF_DIR) && set -a && . ../../$(ENV_FILE) && set +a && \
		terraform init -reconfigure \
		-backend-config="bucket=$${TF_STATE_BUCKET}" \
		-backend-config="region=$${AWS_REGION}"

# Plan/apply: load .env first so AWS_* and TF_* are set.
tf-plan:
	@cd $(TF_DIR) && set -a && . ../../$(ENV_FILE) && set +a && terraform plan -out=tfplan

tf-apply:
	@cd $(TF_DIR) && set -a && . ../../$(ENV_FILE) && set +a && terraform apply
