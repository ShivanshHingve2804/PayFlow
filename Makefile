.PHONY: install test test-cov lint format migrate run docker-up docker-down clean

install:
	pip install -e '.[dev]'

migrate:
	alembic upgrade head

test:
	pytest -v --tb=short

test-cov:
	pytest --cov=app --cov-report=term-missing --cov-report=html

lint:
	ruff check .
	ruff format --check .
	mypy app/

format:
	ruff check --fix .
	ruff format .

run:
	uvicorn app.main:app --reload --port 8000

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
