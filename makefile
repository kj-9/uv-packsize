.PHONY: format lint typecheck test check ci-check build

UV_RUN=uv run --frozen

sync:
	uv sync

readme:
	$(UV_RUN) cog -r README.md

format:
	$(UV_RUN) ruff format .

lint:
	$(UV_RUN) ruff check . --fix

typecheck:
	$(UV_RUN) ty check

test:
	$(UV_RUN) pytest

ci-check:
	$(UV_RUN) ruff format . --check
	$(UV_RUN) ruff check .
	$(UV_RUN) ty check
	$(UV_RUN) cog --check README.md

check: readme format lint typecheck test

build:
	uv build --frozen