.PHONY: install run test test-integration lint typecheck fmt migrate up down build

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -m "not integration"

test-integration:
	pytest -m integration

lint:
	ruff check .

fmt:
	ruff check --fix . && ruff format .

typecheck:
	mypy app

migrate:
	alembic upgrade head

up:
	docker compose up --build

down:
	docker compose down -v

build:
	docker build -t conductor-control-api:local .
