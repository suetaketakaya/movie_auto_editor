FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ backend/src/
COPY alembic/ backend/alembic/
COPY alembic.ini backend/

EXPOSE 8000

CMD ["uvicorn", "backend.src.adapters.inbound.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
