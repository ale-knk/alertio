#!/bin/bash
# Script para ejecutar daily-run de Alertio
# Usado por cron job diario

cd /opt/alertio/deployment/docker
docker-compose run --rm alertio python -m alertio.cli daily-run \
    -c /app/deployment/config/daily-prod.yaml \
    --db /app/data/alertio.sqlite3 \
    >> /opt/alertio/logs/daily.log 2>&1
