SHELL := /bin/bash

# ---- Config ----
PY := uv run
UV := uv

# Services
AGENT_DIR := services/agent-api
KNOW_DIR  := services/mcp-travel-knowledge
PROD_DIR  := services/mcp-travel-products
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
	@echo "  make test-agent | test-knowledge | test-products | test-ingestion"
	@echo "  make run-agent                   - Run FastAPI agent runtime"
	@echo "  make run-knowledge               - Run MCP travel-knowledge server"
	@echo "  make run-products                - Run MCP travel-products server"
	@echo "  make eval                        - Run eval harness, write to data/eval/run.jsonl"
	@echo "  make run-ingestion               - Run ingestion worker (local mode)"
	@echo "  make tf-fmt | tf-validate        - Terraform formatting and validation"
	@echo ""

# ---- Bootstrap ----
.PHONY: bootstrap sync-agent sync-knowledge sync-products sync-ingestion
bootstrap: sync-agent sync-knowledge sync-products sync-ingestion

sync-agent:
	@echo "==> Sync $(AGENT_DIR) (with dev extras)"
	@cd $(AGENT_DIR) && $(UV) sync --extra dev

sync-knowledge:
	@echo "==> Sync $(KNOW_DIR) (with dev extras)"
	@cd $(KNOW_DIR) && $(UV) sync --extra dev

sync-products:
	@echo "==> Sync $(PROD_DIR) (with dev extras)"
	@cd $(PROD_DIR) && $(UV) sync --extra dev

sync-ingestion:
	@echo "==> Sync $(ING_DIR) (with dev extras)"
	@cd $(ING_DIR) && $(UV) sync --extra dev

# ---- Quality ----
.PHONY: fmt lint test
fmt: bootstrap
	@cd $(AGENT_DIR) && $(PY) ruff format .
	@cd $(KNOW_DIR)  && $(PY) ruff format .
	@cd $(PROD_DIR)  && $(PY) ruff format .
	@cd $(ING_DIR)   && $(PY) ruff format .

lint: bootstrap
	@cd $(AGENT_DIR) && $(PY) ruff check .
	@cd $(KNOW_DIR)  && $(PY) ruff check .
	@cd $(PROD_DIR)  && $(PY) ruff check .
	@cd $(ING_DIR)   && $(PY) ruff check .

test: test-agent test-knowledge test-products test-ingestion

test-agent: sync-agent
	@cd $(AGENT_DIR) && $(PY) python -m pytest -q

test-knowledge: sync-knowledge
	@cd $(KNOW_DIR) && $(PY) python -m pytest -q

test-products: sync-products
	@cd $(PROD_DIR) && $(PY) python -m pytest -q

test-ingestion: sync-ingestion
	@cd $(ING_DIR) && $(PY) python -m pytest -q

# ---- Run (local dev) ----
# Load configs/.env so WEAVIATE_* etc. are set (run from repo root)
ENV_FILE := configs/.env

.PHONY: run-agent run-knowledge run-products run-ingestion
run-agent: sync-agent
	@cd $(AGENT_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8000

run-knowledge: sync-knowledge
	@cd $(KNOW_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8010

run-products: sync-products
	@cd $(PROD_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) uvicorn app.main:app --reload --port 8020

run-ingestion: sync-ingestion
	@cd $(ING_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) python -m app.main

.PHONY: eval
eval: sync-agent
	@cd $(AGENT_DIR) && set -a && . ../../$(ENV_FILE) && set +a && $(PY) python -m app.eval_runner --out ../../data/eval/run.jsonl

# ---- Terraform ----
.PHONY: tf-fmt tf-validate
tf-fmt:
	@cd $(TF_DIR) && terraform fmt -recursive

tf-validate:
	@cd $(TF_DIR) && terraform validate
