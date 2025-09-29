# src/alertio/config.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import yaml
import os
from pathlib import Path

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    # Buscar .env en el directorio actual y directorios padre
    dotenv_path = Path.cwd()
    for _ in range(3):  # Buscar hasta 3 niveles hacia arriba
        env_file = dotenv_path / '.env'
        if env_file.exists():
            load_dotenv(env_file)
            break
        dotenv_path = dotenv_path.parent
    else:
        # Si no encuentra .env, cargar desde el directorio actual por defecto
        load_dotenv()
except ImportError:
    # python-dotenv no está instalado, continuar sin cargar .env
    pass

@dataclass
class Ticker:
    symbol: str
    provider: str = "yfinance"
    alias: Optional[str] = None

@dataclass
class ReturnThresholdConfig:
    """Configuración de umbrales de retornos por ventana de tiempo"""
    window: int
    min_threshold: Optional[float] = None  # umbral mínimo (caídas)
    max_threshold: Optional[float] = None  # umbral máximo (subidas)

@dataclass  
class ReturnsConfig:
    """Configuración para alertas basadas en retornos"""
    windows: List[int] = field(default_factory=lambda: [1, 5, 10, 20])
    thresholds: List[ReturnThresholdConfig] = field(default_factory=lambda: [
        ReturnThresholdConfig(window=1, min_threshold=-0.05, max_threshold=0.05),
        ReturnThresholdConfig(window=5, min_threshold=-0.10, max_threshold=0.10),
        ReturnThresholdConfig(window=10, min_threshold=-0.15, max_threshold=0.15),
        ReturnThresholdConfig(window=20, min_threshold=-0.20, max_threshold=0.20),
    ])

@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    parse_mode: str = "HTML"  # or MarkdownV2

@dataclass  
class AlertTypeConfig:
    """Configuración específica por tipo de alerta"""
    enabled: bool = True
    cooldown_days: Optional[int] = None  # Si es None, usa el global

@dataclass
class AlertsConfig:
    cooldown_days: int = 7  # Cooldown global por defecto
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    
    # Configuraciones específicas por tipo
    drop_alerts: AlertTypeConfig = field(default_factory=AlertTypeConfig)
    rise_alerts: AlertTypeConfig = field(default_factory=AlertTypeConfig) 
    weekly_summary: AlertTypeConfig = field(default_factory=lambda: AlertTypeConfig(cooldown_days=7))

@dataclass
class Settings:
    lookback_days: int = 400
    tickers: List[Ticker] = field(default_factory=list)
    returns: ReturnsConfig = field(default_factory=ReturnsConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)

def _to_tickers(raw: List[Dict[str, Any]]) -> List[Ticker]:
    return [Ticker(**item) for item in raw]

def _to_return_thresholds(raw: List[Dict[str, Any]]) -> List[ReturnThresholdConfig]:
    """Convierte configuración raw de umbrales a objetos ReturnThresholdConfig"""
    return [ReturnThresholdConfig(**item) for item in raw]

def _expand_env_vars(value: Any) -> Any:
    """
    Expande variables de entorno en strings con formato ${VAR_NAME} o $VAR_NAME.
    
    Args:
        value: Valor que puede contener variables de entorno
        
    Returns:
        Valor con variables de entorno expandidas
    """
    if isinstance(value, str):
        # Expandir variables de entorno usando os.path.expandvars
        expanded = os.path.expandvars(value)
        # Si la variable no existe, expandvars devuelve el string original
        # Verificar si realmente se expandió
        if expanded != value or not ('$' in value):
            return expanded
        # Si contiene ${VAR} pero no se expandió, la variable no existe
        return expanded
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    else:
        return value

def load_settings(path: str | Path) -> Settings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    
    # Expandir variables de entorno en toda la configuración
    data = _expand_env_vars(data)
    
    # Configuración de retornos
    returns_data = data.get("returns", {})
    
    # Si no hay configuración de returns en absoluto, usar defaults completos
    if not returns_data:
        returns_config = ReturnsConfig()
    else:
        # Si hay configuración, usar lo especificado (incluyendo listas vacías)
        returns_config = ReturnsConfig(
            windows=returns_data.get("windows", [1, 5, 10, 20]),
            thresholds=_to_return_thresholds(returns_data.get("thresholds", []))
        )
    
    # Configuración de Telegram con variables de entorno expandidas
    telegram_config = data.get("alerts", {}).get("telegram", {})
    
    # Configuración de alertas
    alerts_data = data.get("alerts", {})
    
    alerts_config = AlertsConfig(
        cooldown_days=alerts_data.get("cooldown_days", 7),
        telegram=TelegramConfig(**telegram_config),
        drop_alerts=AlertTypeConfig(**alerts_data.get("drop_alerts", {})),
        rise_alerts=AlertTypeConfig(**alerts_data.get("rise_alerts", {})),
        weekly_summary=AlertTypeConfig(**alerts_data.get("weekly_summary", {}))
    )
    
    settings = Settings(
        lookback_days=data.get("lookback_days", 400),
        tickers=_to_tickers(data.get("tickers", [])),
        returns=returns_config,
        alerts=alerts_config,
    )
    return settings