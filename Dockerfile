FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN mkdir -p /data

ENV FLASK_APP=wsgi.py
ENV BEHIND_PROXY=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --spider -q http://localhost:8080/health || exit 1

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "wsgi:app"]
