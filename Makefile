.PHONY: lint
lint:
	black . --check --exclude proto
	flake8
	mypy .
