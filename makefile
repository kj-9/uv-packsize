.PHONY: format lint typecheck test docs docs-check check ci-check build verify-build

UV_RUN=uv run --locked

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

docs:
	$(UV_RUN) mkdocs build --strict

docs-check:
	@site_dir="$$(mktemp -d)"; trap 'rm -rf "$$site_dir"' EXIT; $(UV_RUN) mkdocs build --strict --site-dir "$$site_dir"

ci-check:
	$(UV_RUN) ruff format . --check
	$(UV_RUN) ruff check .
	$(UV_RUN) ty check
	$(UV_RUN) cog --check --diff README.md
	$(MAKE) docs-check

check: readme format lint typecheck test

build:
	uv build --no-sources

verify-build: build
	$(UV_RUN) python scripts/verify_build.py dist
