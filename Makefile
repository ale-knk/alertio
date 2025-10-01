# Makefile.test - Testing CLI Commands
# Uso: make -f Makefile.test <comando>

.PHONY: help test-all scan alert daily weekly scan-csv daily-csv configs clean-db deploy

# Variables
PYTHON := poetry run python
CLI := $(PYTHON) -m alertio.cli
DB := data/test.sqlite3
CSV_OUT := test-output
DROPLET_IP := 159.89.4.130

# Configuraciones de ejemplo
SCAN_CONFIG := config/scan-example.yaml
ALERT_CONFIG := config/alert-example.yaml
DAILY_CONFIG := config/daily-run-example.yaml
WEEKLY_CONFIG := config/weekly-summary-example.yaml

# Colores
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m

help: ## Mostrar ayuda de comandos de testing
	@echo "$(BLUE)🧪 Alertio CLI Testing$(NC)"
	@echo ""
	@echo "$(YELLOW)Comandos básicos:$(NC)"
	@echo "  make -f Makefile.test scan       # Probar comando scan"
	@echo "  make -f Makefile.test alert      # Probar comando alert"  
	@echo "  make -f Makefile.test daily      # Probar comando daily-run"
	@echo "  make -f Makefile.test weekly     # Probar comando weekly-summary"
	@echo ""
	@echo "$(YELLOW)Con CSV output:$(NC)"
	@echo "  make -f Makefile.test scan-csv   # Scan con CSV output"
	@echo "  make -f Makefile.test daily-csv  # Daily-run con CSV output"
	@echo ""
	@echo "$(YELLOW)Utilidades:$(NC)"
	@echo "  make -f Makefile.test test-all   # Probar todos los comandos"
	@echo "  make -f Makefile.test configs    # Validar todas las configuraciones"
	@echo "  make -f Makefile.test clean-db   # Limpiar base de datos de test"
	@echo ""
	@echo "$(YELLOW)Deployment:$(NC)"
	@echo "  make -f Makefile.test deploy           # Deploy a DigitalOcean droplet"
	@echo "  make -f Makefile.test undeploy         # Undeploy completo (elimina todo)"
	@echo "  make -f Makefile.test undeploy-keep-data # Undeploy manteniendo datos"

##@ Comandos CLI

scan: ## Probar comando scan (solo visualización)
	@echo "$(BLUE)📊 Testing: alertio scan$(NC)"
	@echo "Config: $(SCAN_CONFIG)"
	$(CLI) scan -c $(SCAN_CONFIG)
	@echo "$(GREEN)✅ Scan completado$(NC)"

alert: ## Probar comando alert (con DB de test)
	@echo "$(BLUE)🚨 Testing: alertio alert$(NC)"
	@echo "Config: $(ALERT_CONFIG)"
	@echo "Database: $(DB)"
	$(CLI) alert -c $(ALERT_CONFIG) --db $(DB)
	@echo "$(GREEN)✅ Alert completado$(NC)"

daily: ## Probar comando daily-run (pipeline completo)
	@echo "$(BLUE)🔄 Testing: alertio daily-run$(NC)"
	@echo "Config: $(DAILY_CONFIG)"
	@echo "Database: $(DB)"
	$(CLI) daily-run -c $(DAILY_CONFIG) --db $(DB)
	@echo "$(GREEN)✅ Daily-run completado$(NC)"

daily-weekly: ## Probar daily-run con resumen semanal
	@echo "$(BLUE)🔄📊 Testing: alertio daily-run --include-weekly$(NC)"
	@echo "Config: $(DAILY_CONFIG)"
	@echo "Database: $(DB)"
	$(CLI) daily-run -c $(DAILY_CONFIG) --db $(DB) --include-weekly
	@echo "$(GREEN)✅ Daily-run con resumen completado$(NC)"

weekly: ## Probar comando weekly-summary
	@echo "$(BLUE)📊 Testing: alertio weekly-summary$(NC)"
	@echo "Config: $(WEEKLY_CONFIG)"
	@echo "Database: $(DB)"
	$(CLI) weekly-summary -c $(WEEKLY_CONFIG) --db $(DB)
	@echo "$(GREEN)✅ Weekly-summary completado$(NC)"

##@ Con CSV Output

scan-csv: ## Scan con salida CSV
	@echo "$(BLUE)📊📄 Testing: alertio scan con CSV$(NC)"
	@mkdir -p $(CSV_OUT)
	$(CLI) scan -c $(SCAN_CONFIG) --csv-out $(CSV_OUT)
	@echo "$(YELLOW)📁 CSV files en: $(CSV_OUT)/$(NC)"
	@ls -la $(CSV_OUT)/ 2>/dev/null || echo "No CSV files generated"
	@echo "$(GREEN)✅ Scan con CSV completado$(NC)"

daily-csv: ## Daily-run con salida CSV
	@echo "$(BLUE)🔄📄 Testing: alertio daily-run con CSV$(NC)"
	@mkdir -p $(CSV_OUT)
	$(CLI) daily-run -c $(DAILY_CONFIG) --db $(DB) --csv-out $(CSV_OUT)
	@echo "$(YELLOW)📁 CSV files en: $(CSV_OUT)/$(NC)"
	@ls -la $(CSV_OUT)/ 2>/dev/null || echo "No CSV files generated"
	@echo "$(GREEN)✅ Daily-run con CSV completado$(NC)"

##@ Testing y Validación

test-all: ## Probar todos los comandos secuencialmente
	@echo "$(BLUE)🧪 Testing todos los comandos CLI$(NC)"
	@echo ""
	@make -f Makefile.test scan
	@echo ""
	@make -f Makefile.test alert
	@echo ""
	@make -f Makefile.test daily
	@echo ""
	@make -f Makefile.test weekly
	@echo ""
	@echo "$(GREEN)✅ Todos los tests completados$(NC)"

configs: ## Validar que todas las configuraciones cargan correctamente
	@echo "$(BLUE)⚙️ Validando configuraciones$(NC)"
	@echo ""
	@echo "$(YELLOW)📄 Validando scan-example.yaml...$(NC)"
	@$(PYTHON) -c "from src.alertio.config import load_settings; s = load_settings('$(SCAN_CONFIG)'); print(f'✅ {len(s.tickers)} tickers, {len(s.returns.thresholds)} thresholds')"
	@echo ""
	@echo "$(YELLOW)📄 Validando alert-example.yaml...$(NC)"
	@$(PYTHON) -c "from src.alertio.config import load_settings; s = load_settings('$(ALERT_CONFIG)'); print(f'✅ {len(s.tickers)} tickers, {len(s.returns.thresholds)} thresholds, telegram: {s.alerts.telegram.enabled}')"
	@echo ""
	@echo "$(YELLOW)📄 Validando daily-run-example.yaml...$(NC)"
	@$(PYTHON) -c "from src.alertio.config import load_settings; s = load_settings('$(DAILY_CONFIG)'); print(f'✅ {len(s.tickers)} tickers, {len(s.returns.thresholds)} thresholds, weekly: {s.alerts.weekly_summary.enabled}')"
	@echo ""
	@echo "$(YELLOW)📄 Validando weekly-summary-example.yaml...$(NC)"
	@$(PYTHON) -c "from src.alertio.config import load_settings; s = load_settings('$(WEEKLY_CONFIG)'); print(f'✅ {len(s.tickers)} tickers, {len(s.returns.thresholds)} thresholds, telegram: {s.alerts.telegram.enabled}')"
	@echo ""
	@echo "$(GREEN)✅ Todas las configuraciones son válidas$(NC)"

##@ Utilidades

show-db: ## Mostrar contenido de la DB de test
	@echo "$(BLUE)🗄️ Contenido de $(DB):$(NC)"
	@if [ -f $(DB) ]; then \
		$(PYTHON) -c "import sqlite3; con = sqlite3.connect('$(DB)'); cur = con.execute('SELECT COUNT(*) FROM alerts_log'); print(f'📊 Total alertas: {cur.fetchone()[0]}'); cur = con.execute('SELECT symbol, rule_key, triggered_at_utc FROM alerts_log ORDER BY id DESC LIMIT 5'); print('📋 Últimas 5 alertas:'); [print(f'  {row[0]} - {row[1]} - {row[2]}') for row in cur.fetchall()]; con.close()"; \
	else \
		echo "$(YELLOW)⚠️ Base de datos no existe$(NC)"; \
	fi

clean-db: ## Limpiar base de datos de test
	@echo "$(BLUE)🧹 Limpiando DB de test...$(NC)"
	@rm -f $(DB) $(DB)-shm $(DB)-wal
	@echo "$(GREEN)✅ DB de test limpiada$(NC)"

clean-csv: ## Limpiar archivos CSV de test
	@echo "$(BLUE)🧹 Limpiando CSV de test...$(NC)"
	@rm -rf $(CSV_OUT)
	@echo "$(GREEN)✅ CSV de test limpiados$(NC)"

clean: clean-db clean-csv ## Limpiar todo (DB + CSV)
	@echo "$(GREEN)✅ Limpieza completa$(NC)"

##@ Comandos Rápidos (sin confirmación)

q-scan: ## Quick scan (sin mensajes)
	@$(CLI) scan -c $(SCAN_CONFIG)

q-alert: ## Quick alert (sin mensajes)
	@$(CLI) alert -c $(ALERT_CONFIG) --db $(DB)

q-daily: ## Quick daily (sin mensajes)
	@$(CLI) daily-run -c $(DAILY_CONFIG) --db $(DB)

q-weekly: ## Quick weekly (sin mensajes)
	@$(CLI) weekly-summary -c $(WEEKLY_CONFIG) --db $(DB)

##@ Deployment

deploy: ## Deploy a DigitalOcean droplet (159.89.4.130)
	@echo "$(BLUE)🚀 Deploying to DigitalOcean droplet$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@echo "$(YELLOW)⚠️  Asegúrate de que:$(NC)"
	@echo "  • Tienes acceso SSH al droplet"
	@echo "  • El archivo .env está configurado con tus tokens"
	@echo "  • El droplet tiene Docker instalado"
	@echo ""
	@read -p "¿Continuar con el deploy? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	@echo "$(BLUE)Iniciando deployment...$(NC)"
	@./deployment/deploy.sh $(DROPLET_IP)
	@echo "$(GREEN)✅ Deploy completado$(NC)"
	@echo ""
	@echo "$(YELLOW)📋 Próximos pasos:$(NC)"
	@echo "  1. Conectar: ssh root@$(DROPLET_IP)"
	@echo "  2. Ver logs: tail -f /opt/alertio/logs/daily.log"
	@echo "  3. Verificar cron: crontab -l"

undeploy: ## Undeploy completo del droplet (elimina todo)
	@echo "$(RED)🛑 Undeploy completo de DigitalOcean droplet$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@echo "$(YELLOW)⚠️  Esto eliminará:$(NC)"
	@echo "  • Todos los containers Docker"
	@echo "  • Todos los cron jobs"
	@echo "  • Todo el código y archivos"
	@echo "  • Base de datos y logs"
	@echo ""
	@read -p "¿Estás seguro de que quieres eliminar TODO? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	@echo "$(BLUE)Iniciando undeploy...$(NC)"
	@./deployment/undeploy.sh $(DROPLET_IP)
	@echo "$(GREEN)✅ Undeploy completado$(NC)"

undeploy-keep-data: ## Undeploy manteniendo datos (logs y base de datos)
	@echo "$(YELLOW)🛑 Undeploy manteniendo datos de DigitalOcean droplet$(NC)"
	@echo "IP: $(DROPLET_IP)"
	@echo ""
	@echo "$(YELLOW)Esto eliminará:$(NC)"
	@echo "  • Todos los containers Docker"
	@echo "  • Todos los cron jobs"
	@echo "  • Código y archivos de configuración"
	@echo ""
	@echo "$(GREEN)Esto mantendrá:$(NC)"
	@echo "  • Base de datos SQLite"
	@echo "  • Archivos de logs"
	@echo ""
	@read -p "¿Continuar? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	@echo "$(BLUE)Iniciando undeploy...$(NC)"
	@./deployment/undeploy.sh $(DROPLET_IP) --keep-data
	@echo "$(GREEN)✅ Undeploy completado (datos preservados)$(NC)"

##@ Tests Unitarios

test: ## Ejecutar todos los tests con pytest
	@echo "$(BLUE)🧪 Ejecutando tests con pytest$(NC)"
	poetry run pytest

test-v: ## Ejecutar tests con salida verbose
	@echo "$(BLUE)🧪 Ejecutando tests (verbose)$(NC)"
	poetry run pytest -v

test-cov: ## Ejecutar tests con reporte de cobertura
	@echo "$(BLUE)🧪 Ejecutando tests con cobertura$(NC)"
	poetry run pytest --cov=src/alertio --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✅ Reporte HTML generado en: htmlcov/index.html$(NC)"

test-cooldown: ## Ejecutar solo tests del módulo cooldown
	@echo "$(BLUE)🧪 Ejecutando tests de cooldown$(NC)"
	poetry run pytest tests/test_cooldown.py -v

test-watch: ## Ejecutar tests en modo watch (requiere pytest-watch)
	@echo "$(BLUE)🧪 Ejecutando tests en modo watch$(NC)"
	poetry run ptw

install-dev: ## Instalar dependencias de desarrollo
	@echo "$(BLUE)📦 Instalando dependencias de desarrollo$(NC)"
	poetry install --with dev
	@echo "$(GREEN)✅ Dependencias instaladas$(NC)"

clean-test: ## Limpiar archivos generados por tests
	@echo "$(BLUE)🧹 Limpiando archivos de test...$(NC)"
	@rm -rf .pytest_cache htmlcov .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ Archivos de test limpiados$(NC)"
