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
	@echo "  make bootstrap                 - Install toolchain + sync deps (per service)"
	@echo "  make fmt                        - Format all python services"
	@echo "  make lint                       - Lint all python services"
	@echo "  make test                       - Run unit tests for all services"
	@echo "  make test-agent | test-knowledge | test-products | test-ingestion"
	@echo "  make run-agent                   - Run FastAPI agent runtime"
	@echo "  make run-knowledge               - Run MCP travel-knowledge server"
	@echo "  make run-products                - Run MCP travel-products server"
	@echo "  make run-ingestion               - Run ingestion worker (local mode)"
	@echo "  make tf-fmt | tf-validate        - Terraform formatting and validation"
	@echo ""

# ---- Bootstrap ----
.PHONY: bootstrap
bootstrap:
	@echo "==> Syncing python dependencies with uv (per service)..."
	@cd $(AGENT_DIR) && $(UV) sync
	@cd $(KNOW_DIR)  && $(UV) sync
	@cd $(PROD_DIR)  && $(UV) sync
	@cd $(ING_DIR)   && $(UV) sync

# ---- Quality ----
.PHONY: fmt lint test
fmt:
	@cd $(AGENT_DIR) && $(PY) ruff format .
	@cd $(KNOW_DIR)  && $(PY) ruff format .
	@cd $(PROD_DIR)  && $(PY) ruff format .
	@cd $(ING_DIR)   && $(PY) ruff format .

lint:
	@cd $(AGENT_DIR) && $(PY) ruff check .
	@cd $(KNOW_DIR)  && $(PY) ruff check .
	@cd $(PROD_DIR)  && $(PY) ruff check .
	@cd $(ING_DIR)   && $(PY) ruff check .

test: test-agent test-knowledge test-products test-ingestion

test-agent:
	@cd $(AGENT_DIR) && $(PY) pytest -q

test-knowledge:
	@cd $(KNOW_DIR) && $(PY) pytest -q

test-products:
	@cd $(PROD_DIR) && $(PY) pytest -q

test-ingestion:
	@cd $(ING_DIR) && $(PY) pytest -q

# ---- Run (local dev) ----
.PHONY: run-agent run-knowledge run-products run-ingestion
run-agent:
	@cd $(AGENT_DIR) && $(PY) uvicorn app.main:app --reload --port 8000

run-knowledge:
	@cd $(KNOW_DIR) && $(PY) python -m app.main

run-products:
	@cd $(PROD_DIR) && $(PY) python -m app.main

run-ingestion:
	@cd $(ING_DIR) && $(PY) python -m app.main

# ---- Terraform ----
.PHONY: tf-fmt tf-validate
tf-fmt:
	@cd $(TF_DIR) && terraform fmt -recursive

tf-validate:
	@cd $(TF_DIR) && terraform validate
