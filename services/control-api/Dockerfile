# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WEB_CONCURRENCY=1
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY --chmod=0755 docker-entrypoint.sh ./docker-entrypoint.sh
USER app
EXPOSE 8000
# Liveness probe hits /livez (process up), not /readyz, so a brief database
# nap on the managed free tier does not flap the container as unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/livez').status==200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
# Worker count is governed by WEB_CONCURRENCY (default 1 for the 512 MB free
# tier). The longer timeout absorbs managed-database cold starts.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--timeout", "120", "--graceful-timeout", "30"]
