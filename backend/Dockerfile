ARG USE_PROXY_SOURCE=false

FROM python:3.11-slim-bookworm AS backend

ARG USE_PROXY_SOURCE

ENV USE_PROXY_SOURCE=${USE_PROXY_SOURCE}

ENV HOME=/root
WORKDIR /app

# Install Poetry
ENV POETRY_VERSION=2.0.1

# Configure Poetry
ENV POETRY_CACHE_DIR=/tmp/poetry_cache
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_VIRTUALENVS_CREATE=true
ENV POETRY_REQUESTS_TIMEOUT=15

# Install dependencies
COPY docker/debian_testing.sources .
RUN cat debian_testing.sources >> /etc/apt/sources.list.d/debian.sources && \
    if [ "$USE_PROXY_SOURCE" = "true" ]; then \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; fi && \
    apt-get update && \
    apt-get install -y curl jq libgl1-mesa-glx libglib2.0-dev build-essential git tk tk-dev tcl tcl-dev && \
    rm -rf /var/lib/apt/lists/*

# if you located in China, you can use aliyun mirror to speed up
RUN if [ "$USE_PROXY_SOURCE" = "true" ]; then \
        pip install --no-cache-dir poetry==${POETRY_VERSION} -i https://mirrors.aliyun.com/pypi/simple/; \
    else \
        pip install --no-cache-dir poetry==${POETRY_VERSION}; \
    fi

# Install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN if [ "$USE_PROXY_SOURCE" = "true" ]; then \
        poetry config repositories.aliyun https://mirrors.aliyun.com/pypi/simple/ && \
        poetry config pypi-token.pypi ""; \
    fi && \
    poetry install --sync --no-cache --no-root --without dev

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV TZ=UTC

COPY .. .

EXPOSE 8080
HEALTHCHECK CMD curl --silent --fail http://localhost:8080/healthcheck | jq -e '.errcode == -1' || exit 1

COPY docker/docker_start.sh .
CMD ["bash", "docker_start.sh"]
