# tests/conftest.py
"""
Configuración compartida para todos los tests de alertio.
Define fixtures comunes que se pueden usar en cualquier test.
"""
import pytest
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from alertio.config import CooldownConfig
from alertio.cooldown import SmartCooldownManager
from alertio.alerts import Alert
from alertio.types import AlertType


@pytest.fixture
def default_cooldown_config():
    """Configuración de cooldown por defecto para tests"""
    return CooldownConfig(
        base_days=3,
        magnitude_cooldowns={"small": 1, "medium": 3, "large": 7},
        window_cooldowns={1: 0.5, 5: 2, 10: 3, 20: 7},
        progressive_enabled=True,
        progressive_multiplier=0.5,
        max_progressive_multiplier=3.0
    )


@pytest.fixture
def cooldown_manager(default_cooldown_config):
    """Manager de cooldown configurado con valores por defecto"""
    return SmartCooldownManager(default_cooldown_config)


@pytest.fixture
def now_utc():
    """Timestamp actual en UTC"""
    return datetime.now(timezone.utc)


@pytest.fixture
def old_alert_time():
    """Timestamp antiguo (hace 30 días) para tests que necesitan verificar cooldown sin estar activo"""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def create_alert(
    symbol: str = "AAPL",
    severity: float = 0.08,
    violated_windows: Optional[List[Dict[str, Any]]] = None,
    alert_type: AlertType = AlertType.RISE,
    timestamp: Optional[datetime] = None
) -> Alert:
    """
    Helper para crear alertas de prueba con metadata realista.
    
    Args:
        symbol: Símbolo del activo
        severity: Severidad máxima (usado para max_severity)
        violated_windows: Lista de ventanas violadas (si None, se genera una por defecto)
        alert_type: Tipo de alerta
        timestamp: Timestamp de la alerta
    
    Returns:
        Alert configurada para testing
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    if violated_windows is None:
        violated_windows = [{
            'window': 5,
            'return_value': severity,
            'threshold': severity * 0.8,
            'threshold_type': 'max' if alert_type == AlertType.RISE else 'min',
            'severity': severity
        }]
    
    total_violations = len(violated_windows)
    max_severity = max((vw['severity'] for vw in violated_windows), default=severity)
    
    return Alert(
        symbol=symbol,
        rule_key=f"symbol_{symbol}_{alert_type.value}",
        message=f"Test alert for {symbol}",
        price=100.0,
        alert_type=alert_type,
        timestamp=timestamp,
        metadata={
            'violated_windows': violated_windows,
            'max_severity': max_severity,
            'total_violations': total_violations,
            'context_returns': {1: 0.01, 5: severity, 10: severity * 1.2, 20: severity * 1.5},
            'price': 100.0,
            'symbol': symbol
        }
    )


# Registrar el helper como fixture también
@pytest.fixture
def alert_factory():
    """Factory fixture para crear alertas de prueba"""
    return create_alert

