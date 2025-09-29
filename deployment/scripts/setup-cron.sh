#!/bin/bash
# Script para configurar cron jobs de Alertio
# Uso: ./setup-cron.sh [REMOTE_DIR]

set -e

# Configuración
REMOTE_DIR=${1:-"/opt/alertio"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[CRON-SETUP]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[INFO]${NC} $1"; }

log "🕐 Configurando cron jobs para Alertio..."

# Verificar que los scripts existen
if [[ ! -f "$REMOTE_DIR/deployment/scripts/run-daily.sh" ]]; then
    echo "Error: No se encuentra $REMOTE_DIR/deployment/scripts/run-daily.sh"
    exit 1
fi

if [[ ! -f "$REMOTE_DIR/deployment/scripts/run-weekly.sh" ]]; then
    echo "Error: No se encuentra $REMOTE_DIR/deployment/scripts/run-weekly.sh"
    exit 1
fi

# Hacer ejecutables los scripts
log "Haciendo ejecutables los scripts..."
chmod +x "$REMOTE_DIR/deployment/scripts/run-daily.sh"
chmod +x "$REMOTE_DIR/deployment/scripts/run-weekly.sh"
success "✓ Scripts configurados como ejecutables"

# Configurar cron jobs
log "Configurando cron jobs..."

# Crear archivo temporal con los nuevos cron jobs
TEMP_CRON=$(mktemp)

# Obtener crontab actual (excluyendo líneas de alertio existentes)
crontab -l 2>/dev/null | grep -v 'alertio' > "$TEMP_CRON" || true

# Añadir nuevos cron jobs
cat >> "$TEMP_CRON" << EOF
# ===== CONFIGURACIÓN DE PRUEBAS (cada minuto) =====
# Alertio - Daily run: cada minuto para pruebas
* * * * * $REMOTE_DIR/deployment/scripts/run-daily.sh

# Alertio - Weekly summary: cada minuto para pruebas
* * * * * $REMOTE_DIR/deployment/scripts/run-weekly.sh

# ===== CONFIGURACIÓN DE PRODUCCIÓN (comentada) =====
# Alertio - Daily run: todos los días a las 9:00 AM (Europe/Madrid)
# 0 9 * * * $REMOTE_DIR/deployment/scripts/run-daily.sh

# Alertio - Weekly summary: domingos a las 10:00 AM (Europe/Madrid)  
# 0 10 * * 0 $REMOTE_DIR/deployment/scripts/run-weekly.sh
EOF

# Instalar nuevo crontab para root (más simple)
log "Configurando cron para root..."
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

success "✓ Cron jobs configurados"

# Mostrar crontab actual
log "📋 Cron jobs actuales:"
crontab -l | grep -A 5 -B 5 'alertio' || crontab -l

echo
success "🎉 ¡Configuración de cron completada!"
echo
warn "📝 HORARIOS CONFIGURADOS:"
echo "  • Daily run:      CADA MINUTO (modo pruebas)"
echo "  • Weekly summary: CADA MINUTO (modo pruebas)"
echo "  • Zona horaria:   Europe/Madrid (configurada en Docker)"
echo
warn "⚠️  MODO PRUEBAS ACTIVO:"
echo "  • Ambos jobs se ejecutan cada minuto"
echo "  • Para producción, edita el script y descomenta las líneas de producción"
echo
warn "🔧 COMANDOS ÚTILES:"
echo "  • Ver cron jobs:    crontab -l"
echo "  • Editar cron:      crontab -e"
echo "  • Logs diarios:     tail -f $REMOTE_DIR/logs/daily.log"
echo "  • Logs semanales:   tail -f $REMOTE_DIR/logs/weekly.log"
