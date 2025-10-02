# Makefile - Alertio CLI Testing & Development
# Uso: make <comando>

.PHONY: help test test-func test-telegram clean deploy prod-daily prod-weekly prod-opportunity prod-logs prod-status

# Variables
PYTHON := poetry run python
CLI := $(PYTHON) -m alertio.cli
DB := data/test.sqlite3
DROPLET_IP := 159.89.4.130

# Colores
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m

help: ## Mostrar ayuda
	@echo "$(BLUE)🚀 Alertio CLI - Comandos Disponibles$(NC)"
	@echo ""
	@echo "$(YELLOW)🧪 Testing:$(NC)"
	@echo "  make test          # Tests unitarios (pytest)"
	@echo "  make test-func     # Tests funcionales (pytest, CLI/configuración)"
	@echo "  make test-telegram # Tests funcionales de Telegram (requiere credenciales)"
	@echo "  make test-cov      # Tests con cobertura de código"
	@echo ""
	@echo "$(YELLOW)🔧 Desarrollo:$(NC)"
	@echo "  make scan          # Probar comando scan"
	@echo "  make alert         # Probar comando alert"
	@echo "  make daily         # Probar comando daily-run"
	@echo "  make weekly        # Probar comando weekly-summary"
	@echo "  make opportunity   # Probar comando opportunity-scan"
	@echo "  make telegram-test # Probar alertas con Telegram"
	@echo ""
	@echo "$(YELLOW)🧹 Utilidades:$(NC)"
	@echo "  make clean         # Limpiar archivos de test"
	@echo "  make configs       # Validar configuraciones"
	@echo ""
	@echo "$(YELLOW)🚀 Deployment:$(NC)"
	@echo "  make deploy        # Deploy a producción"
	@echo "  make undeploy      # Undeploy completo"
	@echo ""
	@echo "$(YELLOW)🏭 Producción (ejecutar en servidor):$(NC)"
	@echo "  make prod-daily     # Ejecutar daily-run en producción"
	@echo "  make prod-weekly    # Ejecutar weekly-summary en producción"
	@echo "  make prod-opportunity # Ejecutar opportunity-scan en producción"
	@echo "  make prod-logs      # Ver logs de producción"
	@echo "  make prod-status    # Ver estado del contenedor"

##@ Testing

test: ## Ejecutar tests unitarios
	@echo "$(BLUE)🧪 Ejecutando tests unitarios$(NC)"
	poetry run pytest tests/unit/ -v

test-func: ## Ejecutar tests funcionales (CLI + configuración)
	@echo "$(BLUE)🧪 Ejecutando tests funcionales$(NC)"
	poetry run pytest tests/functional -m "cli or config"

test-telegram: ## Ejecutar tests funcionales de Telegram (requiere credenciales)
	@echo "$(BLUE)🤖 Ejecutando tests funcionales de Telegram$(NC)"
	poetry run pytest tests/functional -m telegram

test-cov: ## Ejecutar tests con cobertura
	@echo "$(BLUE)🧪 Ejecutando tests con cobertura$(NC)"
	poetry run pytest --cov=src/alertio --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✅ Reporte HTML: htmlcov/index.html$(NC)"

##@ Desarrollo

scan: ## Probar comando scan
	@echo "$(BLUE)📊 Testing: alertio scan$(NC)"
	$(CLI) scan -c tests/configs/test-scan.yaml

alert: ## Probar comando alert
	@echo "$(BLUE)🚨 Testing: alertio alert$(NC)"
	$(CLI) alert -c tests/configs/test-alert.yaml --db $(DB)

daily: ## Probar comando daily-run
	@echo "$(BLUE)🔄 Testing: alertio daily-run$(NC)"
	$(CLI) daily-run -c tests/configs/test-daily.yaml --db $(DB)

weekly: ## Probar comando weekly-summary
	@echo "$(BLUE)📊 Testing: alertio weekly-summary$(NC)"
	$(CLI) weekly-summary -c tests/configs/test-weekly.yaml --db $(DB)

opportunity: ## Probar comando opportunity-scan
	@echo "$(BLUE)🎯 Testing: alertio opportunity-scan$(NC)"
	$(CLI) opportunity-scan -c tests/configs/test-opportunity.yaml 

telegram-test: ## Probar alertas con Telegram (requiere variables de entorno)
	@echo "$(BLUE)🤖 Testing: alertio alert con Telegram$(NC)"
	@if [ -z "$$TELEGRAM_BOT_TOKEN" ] || [ -z "$$TELEGRAM_CHAT_ID" ]; then \
		echo "$(YELLOW)⚠️  Variables de entorno no configuradas$(NC)"; \
		echo "Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID"; \
		echo "Ejemplo: export TELEGRAM_BOT_TOKEN=tu_token"; \
		echo "         export TELEGRAM_CHAT_ID=tu_chat_id"; \
		exit 1; \
	fi
	$(CLI) alert -c tests/configs/test-telegram.yaml --db $(DB)

##@ Utilidades

clean: ## Limpiar archivos de test
	@echo "$(BLUE)🧹 Limpiando archivos de test...$(NC)"
	@rm -f $(DB) $(DB)-shm $(DB)-wal
	@rm -rf tests/reports/*.json
	@echo "$(GREEN)✅ Limpieza completada$(NC)"

configs: ## Validar configuraciones
	@echo "$(BLUE)⚙️ Validando configuraciones$(NC)"
	@$(PYTHON) -c "from src.alertio.config import load_settings; [load_settings(f'tests/configs/test-{name}.yaml') for name in ['scan', 'alert', 'daily', 'weekly', 'opportunity']]; print('✅ Todas las configuraciones son válidas')"

##@ Deployment

deploy: ## Deploy a producción
	@echo "$(BLUE)🚀 Deploying to DigitalOcean droplet$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@echo "$(YELLOW)⚠️  Asegúrate de que:$(NC)"
	@echo "  • Tienes acceso SSH al droplet"
	@echo "  • El archivo .env está configurado"
	@echo "  • El droplet tiene Docker instalado"
	@echo ""
	@read -p "¿Continuar? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	@echo "$(BLUE)Iniciando deployment...$(NC)"
	@./deployment/deploy.sh $(DROPLET_IP)
	@echo "$(GREEN)✅ Deploy completado$(NC)"

undeploy: ## Undeploy completo
	@echo "$(RED)🛑 Undeploy completo$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@echo "$(YELLOW)⚠️  Esto eliminará TODO del droplet$(NC)"
	@echo ""
	@read -p "¿Estás seguro? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	@echo "$(BLUE)Iniciando undeploy...$(NC)"
	@./deployment/undeploy.sh $(DROPLET_IP)
	@echo "$(GREEN)✅ Undeploy completado$(NC)"

##@ Producción

prod-daily: ## Ejecutar daily-run en producción
	@echo "$(BLUE)🏭 Ejecutando daily-run en producción$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@ssh root@$(DROPLET_IP) "cd /opt/alertio/deployment/scripts && ./run-daily.sh"
	@echo "$(GREEN)✅ Daily-run ejecutado en producción$(NC)"
	@echo "$(YELLOW)📋 Ver logs: ssh root@$(DROPLET_IP) 'tail -f /opt/alertio/logs/daily.log'$(NC)"

prod-weekly: ## Ejecutar weekly-summary en producción
	@echo "$(BLUE)🏭 Ejecutando weekly-summary en producción$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@ssh root@$(DROPLET_IP) "cd /opt/alertio/deployment/scripts && ./run-weekly.sh"
	@echo "$(GREEN)✅ Weekly-summary ejecutado en producción$(NC)"
	@echo "$(YELLOW)📋 Ver logs: ssh root@$(DROPLET_IP) 'tail -f /opt/alertio/logs/weekly.log'$(NC)"

prod-opportunity: ## Ejecutar opportunity-scan en producción
	@echo "$(BLUE)🏭 Ejecutando opportunity-scan en producción$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@ssh root@$(DROPLET_IP) "cd /opt/alertio/deployment/scripts && ./run-opportunity.sh"
	@echo "$(GREEN)✅ Opportunity-scan ejecutado en producción$(NC)"
	@echo "$(YELLOW)📋 Ver logs: ssh root@$(DROPLET_IP) 'tail -f /opt/alertio/logs/opportunity.log'$(NC)"

prod-logs: ## Ver logs de producción
	@echo "$(BLUE)📋 Mostrando logs de producción$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@echo "$(YELLOW)📊 Logs disponibles:$(NC)"
	@echo "  • daily.log      - Logs del proceso diario"
	@echo "  • weekly.log     - Logs del resumen semanal"
	@echo "  • opportunity.log - Logs del análisis de oportunidades"
	@echo ""
	@echo "$(YELLOW)🔍 Comandos útiles:$(NC)"
	@echo "  ssh root@$(DROPLET_IP) 'tail -f /opt/alertio/logs/daily.log'"
	@echo "  ssh root@$(DROPLET_IP) 'tail -f /opt/alertio/logs/weekly.log'"
	@echo "  ssh root@$(DROPLET_IP) 'tail -f /opt/alertio/logs/opportunity.log'"
	@echo "  ssh root@$(DROPLET_IP) 'ls -la /opt/alertio/logs/'"

prod-status: ## Ver estado del contenedor en producción
	@echo "$(BLUE)🔍 Verificando estado del contenedor$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@ssh root@$(DROPLET_IP) "cd /opt/alertio/deployment/docker && docker-compose ps"
	@echo ""
	@echo "$(YELLOW)📊 Información adicional:$(NC)"
	@ssh root@$(DROPLET_IP) "cd /opt/alertio/deployment/docker && docker-compose logs --tail=10 alertio"