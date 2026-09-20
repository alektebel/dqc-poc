FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    REGLLM_ROUTERS=dqc,revisions

COPY requirements-dqc.txt .
RUN pip install -r requirements-dqc.txt

# API + the four screens it serves (one image, one process, one port)
COPY src/ ./src/
COPY api/ ./api/
COPY web/ ./web/
COPY training/__init__.py ./training/__init__.py
COPY training/dq/ ./training/dq/
COPY config.yaml ./config.yaml

# Runtime state: the checks database and the revisions' uploaded files.
# Bind-mount ./data to keep them across container restarts.
RUN mkdir -p data/dq data/revisions

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
