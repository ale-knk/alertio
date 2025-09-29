#!/bin/bash
# Script de deployment simplificado para Alertio v2
# Uso: ./deployment/deploy.sh SERVER_IP

set -e

# Configuración
SERVER_IP=${1:-""}
SERVER_USER="root"
REMOTE_DIR="/opt/alertio"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[DEPLOY]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Validaciones
if [ -z "$SERVER_IP" ]; then
    error "Uso: $0 SERVER_IP"
fi

log "🚀 Desplegando Alertio v2 en $SERVER_IP..."

# Verificar conexión SSH
log "Verificando conexión SSH..."
if ! ssh -o ConnectTimeout=10 $SERVER_USER@$SERVER_IP "echo 'SSH OK'" > /dev/null; then
    error "No se puede conectar via SSH a $SERVER_IP"
fi
success "✓ Conexión SSH verificada"

# Instalar Docker si es necesario (una sola vez)
log "Verificando Docker en el servidor..."
ssh $SERVER_USER@$SERVER_IP "
    if ! command -v docker &> /dev/null; then
        echo 'Instalando Docker...'
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
    fi
    if ! command -v docker-compose &> /dev/null; then
        echo 'Instalando Docker Compose...'
        curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
"
success "✓ Docker configurado"

# Crear directorio base y subdirectorios necesarios
log "Creando directorios necesarios..."
ssh $SERVER_USER@$SERVER_IP "
    mkdir -p $REMOTE_DIR/{data,logs}
    # Configurar permisos para que Docker pueda escribir
    chmod -R 777 $REMOTE_DIR/{data,logs}
"

# Copiar solo archivos esenciales para producción
log "📦 Copiando archivos esenciales..."
rsync -av --delete \
    "$PROJECT_ROOT/deployment/" $SERVER_USER@$SERVER_IP:$REMOTE_DIR/deployment/
rsync -av --delete --exclude='__pycache__' --exclude='*.pyc' \
    "$PROJECT_ROOT/src/" $SERVER_USER@$SERVER_IP:$REMOTE_DIR/src/
rsync -av \
    "$PROJECT_ROOT/pyproject.toml" $SERVER_USER@$SERVER_IP:$REMOTE_DIR/
rsync -av \
    "$PROJECT_ROOT/poetry.lock" $SERVER_USER@$SERVER_IP:$REMOTE_DIR/
rsync -av \
    "$PROJECT_ROOT/README.md" $SERVER_USER@$SERVER_IP:$REMOTE_DIR/

success "✓ Archivos esenciales copiados"

# Configurar permisos de archivos copiados
log "Configurando permisos de archivos..."
ssh $SERVER_USER@$SERVER_IP "
    chmod +x $REMOTE_DIR/deployment/scripts/*.sh
    # Asegurar que los directorios de datos sean escribibles
    chmod -R 777 $REMOTE_DIR/{data,logs}
"

# Copiar .env si existe en el proyecto
log "Configurando variables de entorno..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    scp "$PROJECT_ROOT/.env" $SERVER_USER@$SERVER_IP:$REMOTE_DIR/deployment/docker/
    success "✓ Archivo .env copiado desde el proyecto"
else
    warn "⚠️  No se encontró .env en el proyecto. Creando template..."
    ssh $SERVER_USER@$SERVER_IP "
        cd $REMOTE_DIR/deployment/docker
        if [ ! -f .env ]; then
            cat > .env << 'EOF'
# Variables de entorno para Alertio
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TZ=Europe/Madrid
EOF
            echo 'Archivo .env template creado. ¡RECUERDA configurar tus tokens!'
        fi
    "
fi

# Construir imagen
log "🐳 Construyendo imagen Docker..."
ssh $SERVER_USER@$SERVER_IP "cd $REMOTE_DIR/deployment/docker && docker-compose build"
success "✓ Imagen construida"

# La base de datos se inicializará automáticamente en el primer uso
log "🗄️  Base de datos se inicializará automáticamente en el primer uso"
success "✓ Base de datos lista para inicialización automática"

# Configurar cron jobs
log "⏰ Configurando cron jobs..."
ssh $SERVER_USER@$SERVER_IP "
    # Hacer ejecutable el script de configuración de cron
    chmod +x $REMOTE_DIR/deployment/scripts/setup-cron.sh
    
    # Ejecutar configuración de cron
    $REMOTE_DIR/deployment/scripts/setup-cron.sh $REMOTE_DIR
"

success "🎉 ¡Deployment completado!"
# echo
# warn "📋 PRÓXIMOS PASOS:"
# echo "1. Conectar al servidor: ssh $SERVER_USER@$SERVER_IP"
# echo "2. Ir al directorio: cd $REMOTE_DIR/deployment/docker"
# echo "3. Configurar tokens: nano .env  # (ya estás en deployment/docker/)"
# echo "4. Probar manualmente:"
# echo "   docker-compose run --rm alertio python -m alertio.cli daily-run -c /app/deployment/config/daily-prod.yaml --db /app/data/alertio.sqlite3"
# echo "5. Ver logs:"
# echo "   tail -f $REMOTE_DIR/logs/daily.log    # Logs diarios"
# echo "   tail -f $REMOTE_DIR/logs/weekly.log   # Logs semanales"
# echo
# echo "🔧 Comandos útiles:"
# echo "  ../scripts/run-daily.sh           # Ejecutar proceso diario manualmente"
# echo "  ../scripts/run-weekly.sh          # Ejecutar resumen semanal manualmente"
# echo "  docker-compose run --rm alertio python -m alertio.cli [comando]"
# echo "  docker-compose logs -f"
# echo "  crontab -l                        # Ver cron jobs configurados"