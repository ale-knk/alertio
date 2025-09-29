#!/bin/bash
# Script para ejecutar weekly-summary de Alertio
# Usado por cron job semanal

cd /opt/alertio/deployment/docker
docker-compose run --rm alertio python -m alertio.cli weekly-summary \
    -c /app/deployment/config/weekly-prod.yaml \
    --db /app/data/alertio.sqlite3 \
    >> /opt/alertio/logs/weekly.log 2>&1
