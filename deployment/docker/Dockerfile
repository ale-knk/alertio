# Dockerfile simplificado para Alertio usando Poetry
# Uso: docker build -f deployment/docker/Dockerfile -t alertio:v2 .

FROM python:3.12-slim

# Instalar Poetry y dependencias del sistema
RUN pip install poetry && \
    apt-get update && apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Configurar Poetry para no crear venv (ya estamos en container)
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_VIRTUALENVS_CREATE=false

# Configurar directorio de trabajo
WORKDIR /app

# Copiar archivos esenciales para producción
COPY pyproject.toml poetry.lock ./
COPY src/ ./src/
COPY README.md ./
COPY deployment/config/ ./deployment/config/

# Instalar dependencias con Poetry
RUN poetry install --only=main && rm -rf $POETRY_CACHE_DIR

# Variables de entorno
ENV TZ=Europe/Madrid
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app/src'); import alertio; sys.exit(0)"

# Comando por defecto
CMD ["python", "-m", "alertio.cli", "daily-run", "-c", "/app/deployment/config/daily-prod.yaml", "--db", "/app/data/alertio.sqlite3"]
