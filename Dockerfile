# ── base: the FastAPI service. Light deps, boots /health fast. ────────────────
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# ── voice: adds the heavy LiveKit + provider SDKs for the live audio worker. ──
# Build/run this target only for the mic pipeline (see docker-compose `live`).
FROM base AS voice
COPY requirements-voice.txt .
RUN pip install -r requirements-voice.txt
CMD ["python", "-m", "agent.interview_agent", "start"]
