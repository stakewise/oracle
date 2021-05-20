.PHONY: lint
lint:
	black . --check --exclude proto
	flake8
lint-mypy:
	mypy .
