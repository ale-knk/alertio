# Tests de Alertio

Suite de tests completa para el proyecto Alertio, organizada en tests unitarios y funcionales.

## 📋 Estructura

```
tests/
├── unit/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_cooldown.py
├── functional/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── test_commands.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── test_configs.py
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_integration.py
│   ├── conftest.py
│   └── utils.py
├── configs/
│   └── test-*.yaml
├── reports/
│   └── functional_test_report_*.json
└── README.md
```

## 🚀 Ejecutar Tests

### Instalación de dependencias

Primero, instala las dependencias de desarrollo:

```bash
poetry install --with dev
# o usando el Makefile
make install-dev
```

### Comandos básicos

```bash
# Tests unitarios (pytest)
make test                    # Ejecutar todos los tests unitarios
make test-v                  # Tests con salida verbose
make test-cov                # Tests con cobertura de código
make test-cooldown           # Solo tests de cooldown

# Functional tests
poetry run pytest tests/functional -m cli
poetry run pytest tests/functional -m telegram
poetry run pytest tests/functional -m config
```

## 📊 Cobertura de Código

Los tests están configurados para generar reportes de cobertura:

```bash
make test-cov
```

Esto generará:
- Reporte en terminal con líneas faltantes
- Reporte HTML en `htmlcov/index.html`

## 🧪 Tests del Módulo Cooldown

El archivo `test_cooldown.py` contiene **más de 40 tests** organizados en clases:

### `TestCooldownBasics`
- ✅ Primera alerta sin cooldown
- ✅ Estructura de CooldownResult

### `TestMagnitudeCooldown`
- ✅ Cooldown por magnitud pequeña (<5%)
- ✅ Cooldown por magnitud mediana (5-15%)
- ✅ Cooldown por magnitud grande (>15%)
- ✅ Límites entre categorías
- ✅ Múltiples violaciones aumentan magnitud

### `TestWindowCooldown`
- ✅ Cooldown por ventana de 1, 5, 10, 20 días
- ✅ Múltiples ventanas usan la más corta
- ✅ Multiplicador por múltiples ventanas

### `TestProgressiveCooldown`
- ✅ Multiplicador progresivo aplicado
- ✅ Límite máximo del multiplicador (3.0x)
- ✅ Deshabilitación del progresivo

### `TestCooldownState`
- ✅ Estado en cooldown con alerta reciente
- ✅ Estado fuera de cooldown con alerta antigua
- ✅ Límites exactos del cooldown
- ✅ Cooldowns cortos en horas

### `TestCombinedCooldown`
- ✅ Magnitud domina sobre ventana
- ✅ Ventana domina sobre magnitud
- ✅ Progresivo multiplica el cooldown base

### `TestCooldownSummary`
- ✅ Resumen cuando no está en cooldown
- ✅ Resumen cuando está en cooldown
- ✅ Tiempo restante en horas

### `TestEdgeCases`
- ✅ Severidad cero
- ✅ Severidad extrema (100%)
- ✅ Alertas consecutivas negativas
- ✅ Ventanas violadas vacías
- ✅ Configuración personalizada
- ✅ Timestamp futuro
- ✅ Alertas DROP vs RISE

### `TestRealWorldScenarios`
- ✅ Stock volátil con múltiples alertas
- ✅ Caída constante con cooldown progresivo
- ✅ Múltiples símbolos independientes

### `TestCooldownIntegration`
- ✅ Integración con estructura real de configuración

## 🔧 Fixtures Disponibles

### En `conftest.py`

```python
# Configuración por defecto
default_cooldown_config

# Manager configurado
cooldown_manager

# Timestamp actual
now_utc

# Factory para crear alertas de prueba
alert_factory
```

### Helper Functions

```python
# Crear alerta personalizada
create_alert(
    symbol="AAPL",
    severity=0.08,
    violated_windows=None,
    alert_type=AlertType.RISE,
    timestamp=None
)
```

## 🎯 Casos Críticos Probados

Los tests cubren casos especialmente importantes para producción:

1. **Prevención de spam**: Alertas consecutivas incrementan el cooldown
2. **Sensibilidad correcta**: Movimientos grandes tienen cooldowns largos
3. **Ventanas apropiadas**: Ventanas cortas tienen cooldowns cortos
4. **Edge cases**: Timestamps futuros, severidades extremas, etc.

## 📈 Métricas de Cobertura

Objetivo: **>90% de cobertura** en el módulo `cooldown.py`

Para verificar la cobertura actual:

```bash
make test-cov
open htmlcov/index.html  # macOS
```

## 🐛 Debugging Tests

Para ejecutar tests con modo debug:

```bash
# Con breakpoint
poetry run pytest tests/test_cooldown.py -v -s --pdb

# Con output de prints
poetry run pytest tests/test_cooldown.py -v -s
```

## 📝 Escribir Nuevos Tests

Ejemplo de estructura para nuevos tests:

```python
class TestNuevaFuncionalidad:
    """Tests para [descripción]"""
    
    def test_caso_basico(self, cooldown_manager):
        """Descripción del caso de prueba"""
        # Arrange
        alert = create_alert(severity=0.08)
        
        # Act
        result = cooldown_manager.calculate_cooldown(alert, None, 0)
        
        # Assert
        assert result.cooldown_days > 0
        assert not result.is_in_cooldown
```

## 🔄 CI/CD

Los tests están configurados para ejecutarse automáticamente en CI/CD usando pytest con las siguientes opciones:

- Verbose mode (`-v`)
- Strict markers (`--strict-markers`)
- Cobertura automática (`--cov`)
- Fallo si cobertura < umbral

## 📚 Referencias

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [freezegun Documentation](https://github.com/spulec/freezegun)

