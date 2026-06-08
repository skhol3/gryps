.PHONY: lint format typecheck test check-all check-tools

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy .

test:
	uv run pytest -v --cov=gryps tests/

check-all: lint typecheck test

# Checks específicos para herramientas de calibración (no parte del runtime)
check-tools:
	uv run ruff check tools/
	uv run mypy tools/
