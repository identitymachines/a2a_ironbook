.PHONY: install run-summarizer run-requester lint fmt

install:
	python -m pip install -r requirements.txt

run-summarizer:
	UVICORN_RELOAD=1 python -m agents.summarizer

run-requester:
	python 0m agents.requester

lint:
	python -m compileall .

fmt:
	@echo "Add black/ruff if desired."
