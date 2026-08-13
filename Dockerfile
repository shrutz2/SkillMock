# Single container: React build served by Flask, so the whole app is one URL.

# ---- Stage 1: build the frontend ----
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same-origin API calls, since Flask serves this build.
ENV REACT_APP_API_URL=""
RUN npm run build

# ---- Stage 2: backend ----
FROM python:3.11-slim

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/user/models

WORKDIR /home/user/app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /build/build ./static

# Bake the embedding model into the image so the first request is not stuck
# downloading it.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')" \
 && mkdir -p /home/user/data \
 && chown -R user:user /home/user

USER user

# Demo defaults: SQLite in a writable path, no external database needed.
# No CORS origin is set because the frontend is served from this same origin.
ENV PORT=7860 \
    DB_BACKEND=sqlite \
    SQLITE_PATH=/home/user/data/skillmock.db \
    EMBEDDING_BACKEND=onnx \
    FLASK_DEBUG=false

EXPOSE 7860

# One worker: FAISS indices live in process memory, so a session's requests must
# land on the same worker. Threads handle concurrency instead.
CMD ["gunicorn", "-w", "1", "-k", "gthread", "--threads", "4", \
     "-t", "300", "-b", "0.0.0.0:7860", "app:app"]
