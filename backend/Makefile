.PHONY: install lint format test test-deep run serve schema check
install:
	uv sync
lint:
	uv run ruff check . && uv run ruff format --check .
format:
	uv run ruff check --fix . && uv run ruff format .
test:
	HYPOTHESIS_PROFILE=ci uv run pytest -q --tb=short
test-deep:
	HYPOTHESIS_PROFILE=deep uv run pytest -q --tb=short
run:
	uv run python manage.py runserver 8000
serve:
	uv run gunicorn -c gunicorn.conf.py config.wsgi
schema:
	DJANGO_DEBUG=true uv run python manage.py spectacular --format openapi-json --validate --file openapi.json
check:
	$(MAKE) lint test
