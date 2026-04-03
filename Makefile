.PHONY: fmt lint test test-integration

fmt:
	@python3 -m compileall src tests

lint:
	@python3 -m compileall src tests

test:
	@PYTHONPATH=src python3 -m pytest tests/unit -v

test-integration:
	@PYTHONPATH=src python3 -m pytest tests/integration -v

