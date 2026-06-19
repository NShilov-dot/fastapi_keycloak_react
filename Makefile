# SaaS (FastAPI + Keycloak + React) — developer task runner.
# Run `make` or `make help` to list targets.

SHELL    := /usr/bin/env bash
COMPOSE  := docker compose
BACKEND  := backend

.DEFAULT_GOAL := help

.PHONY: help env gen-key up down restart build logs ps clean \
        migrate revision psql redis-cli backend-shell \
        test lint fmt typecheck check \
        fe-install fe-build fe-dev dev-backend

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------

env: ## Scaffold ./.env from backend/.env.example with a fresh encryption key
	@if [ -f .env ]; then \
	  echo ".env already exists — not overwriting"; \
	else \
	  cp $(BACKEND)/.env.example .env; \
	  key=$$($(MAKE) -s gen-key); \
	  printf '\nSESSION_ENCRYPTION_KEYS=%s\n' "$$key" >> .env; \
	  echo "Created .env (with a generated SESSION_ENCRYPTION_KEYS)."; \
	  echo "Review hostnames: localhost for local dev, compose overrides for docker."; \
	fi

gen-key: ## Print a fresh base64 AES-256 key for SESSION_ENCRYPTION_KEYS
	@cd $(BACKEND) && PYTHONPATH=src .venv/bin/python -c \
	  "from app.core.crypto import generate_key; print(generate_key())"

# --------------------------------------------------------------------------
# Docker stack lifecycle
# --------------------------------------------------------------------------

up: ## Build & start the full stack (postgres, keycloak, redis, app, frontend)
	$(COMPOSE) up -d --build

down: ## Stop the stack (keep volumes/data)
	$(COMPOSE) down

restart: down up ## Restart the stack

build: ## Build all images
	$(COMPOSE) build

logs: ## Tail logs (one service: make logs svc=app)
	$(COMPOSE) logs -f $(svc)

ps: ## Show running services
	$(COMPOSE) ps

clean: ## Stop the stack AND remove volumes (DESTROYS db/redis data)
	$(COMPOSE) down -v

# --------------------------------------------------------------------------
# Database / Keycloak / Redis (inside the running stack)
# --------------------------------------------------------------------------

migrate: ## Apply public-schema migrations (two-head setup: public + tenant branches)
	$(COMPOSE) exec app alembic -x scope=public upgrade public@head

revision: ## Autogenerate a migration: make revision m="message"
	$(COMPOSE) exec app alembic revision --autogenerate -m "$(m)"

psql: ## Open psql in the postgres container
	$(COMPOSE) exec postgres psql -U app -d app

redis-cli: ## Open redis-cli in the redis container
	$(COMPOSE) exec redis redis-cli

backend-shell: ## Open a shell in the app container
	$(COMPOSE) exec app bash

# --------------------------------------------------------------------------
# Quality gates (local venv)
# --------------------------------------------------------------------------

test: ## Run backend tests
	cd $(BACKEND) && PYTHONPATH=src .venv/bin/python -m pytest tests -q

lint: ## ruff lint (backend)
	cd $(BACKEND) && .venv/bin/ruff check src tests

fmt: ## ruff autofix + format (backend)
	cd $(BACKEND) && .venv/bin/ruff check --fix src tests && .venv/bin/ruff format src tests

typecheck: ## mypy (backend)
	cd $(BACKEND) && PYTHONPATH=src .venv/bin/mypy src

check: lint typecheck test ## Run lint + typecheck + tests

# --------------------------------------------------------------------------
# Frontend
# --------------------------------------------------------------------------

fe-install: ## Install frontend deps (npm ci)
	cd frontend && npm ci

fe-build: ## Build the frontend production bundle
	cd frontend && npm run build

fe-dev: ## Run the Vite dev server
	cd frontend && npm run dev

# --------------------------------------------------------------------------
# Local (non-docker) backend dev — loads ./.env, talks to docker-exposed ports
# --------------------------------------------------------------------------

dev-backend: ## Run uvicorn locally with reload (needs `make up` for postgres/redis/keycloak)
	cd $(BACKEND) && set -a && . ../.env && set +a && \
	  PYTHONPATH=src .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
