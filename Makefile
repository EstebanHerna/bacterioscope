.PHONY: install test lint typecheck clean data demo

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src/bacterioscope --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

typecheck:
	mypy src/bacterioscope/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage dist build

data:
	python scripts/download_data.py

demo:
	streamlit run src/bacterioscope/app.py

api:
	uvicorn bacterioscope.api.routes:app --reload

all: install lint typecheck test
