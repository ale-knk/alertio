#!/bin/bash
# Script de undeploy para Alertio v2
# Uso: ./deployment/undeploy.sh SERVER_IP [--keep-data]

set -e

# Configuración
SERVER_IP=${1:-""}
KEEP_DATA=${2:-""}
SERVER_USER="root"
REMOTE_DIR="/opt/alertio"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[UNDEPLOY]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Validaciones
if [ -z "$SERVER_IP" ]; then
    error "Uso: $0 SERVER_IP [--keep-data]"
fi

log "🛑 Desinstalando Alertio v2 de $SERVER_IP..."

# Verificar conexión SSH
log "Verificando conexión SSH..."
if ! ssh -o ConnectTimeout=10 $SERVER_USER@$SERVER_IP "echo 'SSH OK'" > /dev/null; then
    error "No se puede conectar via SSH a $SERVER_IP"
fi
success "✓ Conexión SSH verificada"

# Parar y eliminar containers Docker
log "🐳 Parando y eliminando containers Docker..."
ssh $SERVER_USER@$SERVER_IP "
    cd $REMOTE_DIR/deployment/docker 2>/dev/null || true
    
    # Parar y eliminar containers
    if [ -f docker-compose.yml ]; then
        docker-compose down --remove-orphans 2>/dev/null || true
        docker-compose rm -f 2>/dev/null || true
    fi
    
    # Eliminar imagen de alertio
    docker rmi alertio:v2 2>/dev/null || true
    
    # Limpiar imágenes huérfanas
    docker image prune -f 2>/dev/null || true
"
success "✓ Containers Docker eliminados"

# Eliminar cron jobs
log "⏰ Eliminando cron jobs..."
ssh $SERVER_USER@$SERVER_IP "
    # Crear backup del crontab actual
    crontab -l > /tmp/crontab_backup_\$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # Eliminar líneas que contengan 'alertio'
    crontab -l 2>/dev/null | grep -v 'alertio' | crontab - 2>/dev/null || true
"
success "✓ Cron jobs eliminados"

# Limpiar archivos del servidor
log "🗑️  Limpiando archivos del servidor..."
if [ "$KEEP_DATA" = "--keep-data" ]; then
    warn "⚠️  Manteniendo datos (logs y base de datos)"
    ssh $SERVER_USER@$SERVER_IP "
        # Eliminar solo código y configs, mantener data/ y logs/
        rm -rf $REMOTE_DIR/deployment/ 2>/dev/null || true
        rm -rf $REMOTE_DIR/src/ 2>/dev/null || true
        rm -f $REMOTE_DIR/pyproject.toml 2>/dev/null || true
        rm -f $REMOTE_DIR/README.md 2>/dev/null || true
        rm -f $REMOTE_DIR/.env 2>/dev/null || true
        
        echo 'Archivos de código eliminados, datos preservados'
    "
else
    log "Eliminando todo el directorio de Alertio..."
    ssh $SERVER_USER@$SERVER_IP "
        rm -rf $REMOTE_DIR 2>/dev/null || true
        echo 'Directorio completo eliminado'
    "
fi
success "✓ Archivos del servidor limpiados"

# Mostrar estado final
log "📊 Estado final del servidor:"
ssh $SERVER_USER@$SERVER_IP "
    echo 'Containers Docker:'
    docker ps -a | grep alertio || echo '  Ningún container de alertio encontrado'
    
    echo
    echo 'Cron jobs:'
    crontab -l | grep alertio || echo '  Ningún cron job de alertio encontrado'
    
    echo
    echo 'Archivos restantes:'
    if [ -d '$REMOTE_DIR' ]; then
        ls -la '$REMOTE_DIR' 2>/dev/null || echo '  Directorio no encontrado'
    else
        echo '  Directorio /opt/alertio eliminado'
    fi
"

success "🎉 ¡Undeploy completado!"
echo
warn "📋 RESUMEN:"
if [ "$KEEP_DATA" = "--keep-data" ]; then
    echo "  • Containers: Eliminados"
    echo "  • Cron jobs: Eliminados" 
    echo "  • Código: Eliminado"
    echo "  • Datos: Preservados en $REMOTE_DIR/data/ y $REMOTE_DIR/logs/"
else
    echo "  • Todo eliminado completamente"
    echo "  • Directorio $REMOTE_DIR removido"
fi
echo
warn "🔧 COMANDOS ÚTILES:"
echo "  • Ver containers: ssh $SERVER_USER@$SERVER_IP 'docker ps -a'"
echo "  • Ver cron jobs: ssh $SERVER_USER@$SERVER_IP 'crontab -l'"
echo "  • Ver archivos: ssh $SERVER_USER@$SERVER_IP 'ls -la $REMOTE_DIR'"
