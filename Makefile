.PHONY: install test test-cov run docker-up docker-down lint clean

install:
	pip install -e '.[dev]'

test:
	pytest -v --tb=short

test-cov:
	pytest --cov=app --cov-report=term-missing --cov-report=html

run:
	uvicorn app.main:app --reload --port 8000

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v

lint:
	ruff check app/ tests/

clean:
	rm -rf __pycache__ .pytest_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
