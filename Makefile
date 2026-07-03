.PHONY: lint format typecheck test test-unit test-int check build

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

typecheck:
	uv run mypy

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit

test-int:
	uv run pytest tests/integration

check: lint typecheck test

build:
	docker build -t change-bridge:local .
