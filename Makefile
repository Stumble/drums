# Convenience wrapper. `make help` lists targets.
.DEFAULT_GOAL := help
VENV := backend/.venv
PY := $(VENV)/bin/python

.PHONY: help up down build logs dev venv test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Build + run with Docker Compose (http://localhost:8000)
	docker compose up --build

down: ## Stop and remove the container
	docker compose down

build: ## Build the Docker image
	docker compose build

logs: ## Tail container logs
	docker compose logs -f

venv: ## Create local venv and install deps (for non-Docker dev)
	python3 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r backend/requirements-dev.txt
	@echo "PDF export also needs the system Cairo lib: sudo apt-get install -y libcairo2"

dev: venv ## Run the API locally with autoreload
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

test: ## Run the test suite locally
	cd backend && .venv/bin/python -m pytest

clean: ## Remove venv and generated artifacts
	rm -rf $(VENV) backend/__pycache__ backend/app/__pycache__ backend/tests/__pycache__
	rm -f backend/*.wav backend/*.pdf backend/*.musicxml
