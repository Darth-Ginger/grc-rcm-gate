FROM python:3.12-slim

ARG BUILD_VERSION=unknown
ENV APP_VERSION=$BUILD_VERSION

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src
COPY docs ./docs
COPY data ./data
COPY webapp ./webapp

ENV PORT=8000
ENV RELOAD=false

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
