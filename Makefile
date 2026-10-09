.PHONY: install dev test

install:
	python3 -m pip install -r requirements.txt

dev:
	uvicorn backend.app.main:app --reload

test:
	pytest
