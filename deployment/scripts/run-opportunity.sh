#!/bin/bash
# Script para ejecutar opportunity-scan de Alertio
# Usado por cron job para análisis de oportunidades de entrada

cd /opt/alertio/deployment/docker
docker-compose run --rm alertio python -m alertio.cli opportunity-scan \
    -c /app/deployment/config/opportunity-prod.yaml \
    --threshold -0.05 \
    --windows 5 10 20 \
    --min-windows 1 \
    >> /opt/alertio/logs/opportunity.log 2>&1
