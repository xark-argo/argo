#* Variables
SHELL := /usr/bin/env bash
PYTHON := python
OS := $(shell python -c "import sys; print(sys.platform)")

POETRY_DIR := backend
PYTHONPATH := $(shell pwd)/$(POETRY_DIR)

ifeq ($(OS),win32)
    TEST_COMMAND := cd $(POETRY_DIR) && set PYTHONPATH=$(PYTHONPATH) && poetry run pytest -c pyproject.toml --cov-report=html:../assets/coverage/htmlcov --cov=. tests/
else
    TEST_COMMAND := cd $(POETRY_DIR) && PYTHONPATH=$(PYTHONPATH) && poetry run pytest -c pyproject.toml --cov-report=html:../assets/coverage/htmlcov --cov=. tests/
endif

#* Docker variables
IMAGE := argo
VERSION := latest
USE_PROXY_SOURCE ?= false

.PHONY: lock install pre-commit-install formatting test check-codestyle check-types lint docker-build docker-remove build-web build-exe migration cleanup help

lock:
	cd $(POETRY_DIR) && poetry lock -n && poetry export --without-hashes > requirements.txt

install:
	cd $(POETRY_DIR) && poetry install -n
pre-commit-install:
	cd $(POETRY_DIR) && poetry run pre-commit install

format:
	cd $(POETRY_DIR) && poetry run ruff format --config ruff.toml .
	cd $(POETRY_DIR) && poetry run ruff check --fix --config ruff.toml .

test:
	$(TEST_COMMAND)
	cd $(POETRY_DIR) && poetry run coverage-badge -o ../assets/images/coverage.svg -f

check-codestyle:
	cd $(POETRY_DIR) && poetry run ruff format --check --config ruff.toml .
	cd $(POETRY_DIR) && poetry run ruff check --config ruff.toml .

check-types:
	cd $(POETRY_DIR) && poetry run mypy . --config-file mypy.ini


lint: test check-codestyle check-types

run:
	cd $(POETRY_DIR) && poetry install -n && \
	poetry run python main.py $(if $(host),--host=$(host)) $(if $(port),--port=$(port))

migration:
	cd $(POETRY_DIR) && poetry run python -m database.migration

build-web:
	rm -rf $(POETRY_DIR)/dist
	cd frontend && rm -rf dist && yarn && npm run build && cp -r dist ../backend

build-exe:
	cd $(POETRY_DIR) && poetry run pyinstaller ../deploy/pyinstaller/argo_build.spec \
		--distpath ../build/output \
		--workpath ../build

# Example: make docker-build VERSION=latest
# Example: make docker-build IMAGE=some_name VERSION=0.1.0 USE_PROXY_SOURCE=true
docker-build:
	@echo Building docker image: $(IMAGE):$(VERSION)
	@echo USE_PROXY_SOURCE: $(USE_PROXY_SOURCE)
	cd $(POETRY_DIR) && docker build \
		-t $(IMAGE):$(VERSION) . \
		-f Dockerfile \
		--no-cache \
		--build-arg USE_PROXY_SOURCE=$(USE_PROXY_SOURCE)

# Example: make docker-remove VERSION=latest
# Example: make docker-remove IMAGE=some_name VERSION=0.1.0
docker-remove:
	@echo Removing docker $(IMAGE):$(VERSION) ...
	docker rmi -f $(IMAGE):$(VERSION)

cleanup:
	find . | grep -E "(__pycache__|\.pyc|\.pyo$$)" | xargs rm -rf
	find . | grep -E ".DS_Store" | xargs rm -rf
	find . | grep -E ".mypy_cache" | xargs rm -rf
	find . | grep -E ".ipynb_checkpoints" | xargs rm -rf
	find . | grep -E ".pytest_cache" | xargs rm -rf
	rm -rf build/

help:
	@echo "lock                                      Lock the dependencies."
	@echo "install                                   Install the project dependencies."
	@echo "pre-commit-install                        Install the pre-commit hooks."
	@echo "format                                    Format the codebase."
	@echo "test                                      Run the tests."
	@echo "check-codestyle                           Check the codebase for style issues."
	@echo "check-types								 Run static type checks using mypy with project configuration."
	@echo "lint                                      Run the tests and check the codebase for style issues."
	@echo "docker-build                              Build the docker image."
	@echo "docker-remove                             Remove the docker image."
	@echo "run [host=HOST] [port=PORT]               Run the main application using the start script"
	@echo "                                          Optional:"
	@echo "                                             host - specify host to bind (e.g. 0.0.0.0)"
	@echo "                                             port - specify port to listen (e.g. 8000)"
	@echo "build-web                                 Build the frontend (git submodule update --init --recursive) and copy output to backend"
	@echo "build-exe                                 Build executable using PyInstaller and deploy/argo_build.spec."
	@echo "migration                                 Run database migrations (e.g. alembic upgrade head)."
	@echo "cleanup                                   Clean the project directory."
	@echo "help                                      Display this help message."
