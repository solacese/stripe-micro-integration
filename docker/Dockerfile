FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /install /usr/local
COPY app ./app
COPY scripts ./scripts
COPY requirements.txt ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD sh -c 'curl -f "http://localhost:${APP_PORT:-8080}/ready" || exit 1'

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
