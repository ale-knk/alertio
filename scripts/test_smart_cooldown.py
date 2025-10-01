#!/usr/bin/env python3
"""
Script de prueba para el sistema de cooldown inteligente.
Demuestra cómo funciona el nuevo sistema con diferentes escenarios.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Agregar el directorio src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alertio.config import load_settings
from alertio.cooldown import SmartCooldownManager, CooldownConfig
from alertio.alerts import Alert
from alertio.types import AlertType


def create_test_alert(symbol: str, return_value: float, window: int, alert_type: AlertType) -> Alert:
    """Crea una alerta de prueba"""
    return Alert(
        symbol=symbol,
        rule_key=f"return_{window}d_{'min' if return_value < 0 else 'max'}_{abs(return_value):.3f}",
        message=f"Retorno {window}d {'≤' if return_value < 0 else '≥'} {return_value:.1%}",
        price=100.0,
        alert_type=alert_type,
        timestamp=datetime.now(timezone.utc),
        metadata={
            'window': window,
            'actual_return': return_value,
            'threshold': return_value * 0.8,  # Simular umbral
            'threshold_type': 'min' if return_value < 0 else 'max',
            'context_returns': {1: 0.01, 5: return_value, 10: return_value * 1.2, 20: return_value * 1.5},
            'price': 100.0,
            'symbol': symbol
        }
    )


def test_cooldown_scenarios():
    """Prueba diferentes escenarios de cooldown"""
    print("🧪 Probando Sistema de Cooldown Inteligente")
    print("=" * 50)
    
    # Configuración de prueba
    config = CooldownConfig(
        base_days=3,
        magnitude_cooldowns={"small": 1, "medium": 3, "large": 7},
        window_cooldowns={1: 0.5, 5: 2, 10: 3, 20: 7},
        progressive_enabled=True,
        progressive_multiplier=0.5,
        max_progressive_multiplier=3.0
    )
    
    manager = SmartCooldownManager(config)
    
    # Escenario 1: Primera alerta (sin cooldown)
    print("\n📊 Escenario 1: Primera alerta")
    alert1 = create_test_alert("AAPL", 0.08, 5, AlertType.RISE)
    result1 = manager.calculate_cooldown(alert1, None, 0)
    print(f"   Alerta: {alert1.symbol} +{alert1.metadata['actual_return']:.1%} en {alert1.metadata['window']}d")
    print(f"   Resultado: {result1.reason}")
    print(f"   Cooldown: {result1.cooldown_days:.1f} días")
    
    # Escenario 2: Alerta pequeña (cooldown corto)
    print("\n📊 Escenario 2: Alerta pequeña")
    alert2 = create_test_alert("AAPL", 0.03, 5, AlertType.RISE)
    last_time = datetime.now(timezone.utc) - timedelta(hours=6)  # Hace 6 horas
    result2 = manager.calculate_cooldown(alert2, last_time, 0)
    print(f"   Alerta: {alert2.symbol} +{alert2.metadata['actual_return']:.1%} en {alert2.metadata['window']}d")
    print(f"   Última alerta: hace 6 horas")
    print(f"   Resultado: {result2.reason}")
    print(f"   En cooldown: {result2.is_in_cooldown}")
    
    # Escenario 3: Alerta grande (cooldown largo)
    print("\n📊 Escenario 3: Alerta grande")
    alert3 = create_test_alert("AAPL", 0.20, 5, AlertType.RISE)
    last_time = datetime.now(timezone.utc) - timedelta(days=2)  # Hace 2 días
    result3 = manager.calculate_cooldown(alert3, last_time, 0)
    print(f"   Alerta: {alert3.symbol} +{alert3.metadata['actual_return']:.1%} en {alert3.metadata['window']}d")
    print(f"   Última alerta: hace 2 días")
    print(f"   Resultado: {result3.reason}")
    print(f"   En cooldown: {result3.is_in_cooldown}")
    
    # Escenario 4: Alerta de ventana corta (cooldown corto)
    print("\n📊 Escenario 4: Alerta de ventana corta")
    alert4 = create_test_alert("AAPL", 0.06, 1, AlertType.RISE)
    last_time = datetime.now(timezone.utc) - timedelta(hours=8)  # Hace 8 horas
    result4 = manager.calculate_cooldown(alert4, last_time, 0)
    print(f"   Alerta: {alert4.symbol} +{alert4.metadata['actual_return']:.1%} en {alert4.metadata['window']}d")
    print(f"   Última alerta: hace 8 horas")
    print(f"   Resultado: {result4.reason}")
    print(f"   En cooldown: {result4.is_in_cooldown}")
    
    # Escenario 5: Alerta de ventana larga (cooldown largo)
    print("\n📊 Escenario 5: Alerta de ventana larga")
    alert5 = create_test_alert("AAPL", 0.06, 20, AlertType.RISE)
    last_time = datetime.now(timezone.utc) - timedelta(days=2)  # Hace 2 días
    result5 = manager.calculate_cooldown(alert5, last_time, 0)
    print(f"   Alerta: {alert5.symbol} +{alert5.metadata['actual_return']:.1%} en {alert5.metadata['window']}d")
    print(f"   Última alerta: hace 2 días")
    print(f"   Resultado: {result5.reason}")
    print(f"   En cooldown: {result5.is_in_cooldown}")
    
    # Escenario 6: Cooldown progresivo (múltiples alertas consecutivas)
    print("\n📊 Escenario 6: Cooldown progresivo")
    alert6 = create_test_alert("AAPL", 0.08, 5, AlertType.RISE)
    last_time = datetime.now(timezone.utc) - timedelta(days=1)  # Hace 1 día
    result6 = manager.calculate_cooldown(alert6, last_time, 3)  # 3 alertas consecutivas
    print(f"   Alerta: {alert6.symbol} +{alert6.metadata['actual_return']:.1%} en {alert6.metadata['window']}d")
    print(f"   Última alerta: hace 1 día")
    print(f"   Alertas consecutivas: 3")
    print(f"   Resultado: {result6.reason}")
    print(f"   En cooldown: {result6.is_in_cooldown}")
    
    # Escenario 7: Comparación de diferentes magnitudes
    print("\n📊 Escenario 7: Comparación de magnitudes")
    for magnitude, label in [(0.02, "pequeño"), (0.08, "mediano"), (0.18, "grande")]:
        alert = create_test_alert("AAPL", magnitude, 5, AlertType.RISE)
        result = manager.calculate_cooldown(alert, None, 0)
        print(f"   {label.capitalize()} ({magnitude:.1%}): {result.cooldown_days:.1f} días")


if __name__ == "__main__":
    test_cooldown_scenarios()
    print("\n✅ Pruebas completadas")
