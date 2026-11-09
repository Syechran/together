# syntax=docker/dockerfile:1.7

FROM python:3.12.7-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

COPY requirements.txt requirements-ml.txt ./
RUN python -m venv /opt/mlvenv \
    && /opt/mlvenv/bin/pip install --upgrade pip==24.2 \
    && /opt/mlvenv/bin/pip install -r requirements-ml.txt

COPY ml/ ./ml/
RUN /opt/mlvenv/bin/python ml/train_model.py --output /build/model


FROM python:3.12.7-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MODEL_PATH=/app/model/model.json

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip==24.2 \
    && /opt/venv/bin/pip install -r requirements.txt \
    && rm -rf /root/.cache/pip

COPY --from=builder /build/model /app/model
COPY app/ ./app/

RUN chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
