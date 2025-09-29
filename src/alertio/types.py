# src/alertio/alert_types.py
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional


class AlertType(Enum):
    """Tipos de alertas disponibles"""
    DROP = "drop"           # Alerta de caída
    RISE = "rise"           # Alerta de subida  


@dataclass
class AlertConfig:
    """Configuración específica por tipo de alerta"""
    enabled: bool = True
    emoji: str = "⚠️"
    color: str = "#FFA500"  # Color para posibles integraciones futuras
    cooldown_days: Optional[int] = None  # Override del cooldown global
    
    
# Configuraciones por defecto para cada tipo
DEFAULT_ALERT_CONFIGS: Dict[AlertType, AlertConfig] = {
    AlertType.DROP: AlertConfig(
        enabled=True,
        emoji="📉",
        color="#FF4444",  # Rojo
        cooldown_days=None  # Usa el global
    ),
    AlertType.RISE: AlertConfig(
        enabled=True, 
        emoji="📈",
        color="#44FF44",  # Verde
        cooldown_days=None  # Usa el global
    )
}


def get_alert_config(alert_type: AlertType) -> AlertConfig:
    """Obtiene la configuración para un tipo de alerta"""
    return DEFAULT_ALERT_CONFIGS.get(alert_type, AlertConfig())


def format_alert_title(alert_type: AlertType, symbol: str) -> str:
    """Formatea el título de la alerta según el tipo"""
    config = get_alert_config(alert_type)
    
    if alert_type == AlertType.DROP:
        return f"{config.emoji} ALERTA CAÍDA - {symbol}"
    elif alert_type == AlertType.RISE:
        return f"{config.emoji} ALERTA SUBIDA - {symbol}"
    else:
        return f"{config.emoji} ALERTA - {symbol}"
