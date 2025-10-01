from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd

from alertio.config import Settings
from alertio.telegram import build_notifier


@dataclass
class MarketSummary:
    """Resumen de mercado para un período específico."""
    period_name: str  # "weekly", "monthly", etc.
    symbols_analyzed: int
    best_performer: Dict[str, Any]
    worst_performer: Dict[str, Any]
    average_return: float
    period_days: int
    summary_data: List[Dict[str, Any]]
    timestamp: datetime

def analyze_market_performance(current_data: Dict[str, pd.Series], period_days: int = 20) -> MarketSummary:
    """
    Analiza el rendimiento general del mercado en un período dado.
    
    Args:
        current_data: Datos actuales por símbolo
        period_days: Período de análisis en días
    
    Returns:
        MarketSummary con el análisis completo
    """
    summary_data = []
    
    # Analizar cada símbolo
    for symbol, row in current_data.items():
        if symbol.startswith("^"):
            continue  # Skip indices for individual analysis, but include in averages
            
        return_col = f"return_{period_days}d"
        if return_col not in row.index:
            continue
            
        symbol_data = {
            'symbol': symbol,
            'price': float(row.get('Close', row.get('close', 0))),  # Manejar ambos casos
            'return_1d': float(row.get('return_1d', 0)) * 100,
            'return_5d': float(row.get('return_5d', 0)) * 100,
            'return_10d': float(row.get('return_10d', 0)) * 100,
            'return_20d': float(row.get('return_20d', 0)) * 100,
        }
        summary_data.append(symbol_data)
    
    if not summary_data:
        # Return empty summary if no data
        return MarketSummary(
            period_name=f"{period_days}d",
            symbols_analyzed=0,
            best_performer={},
            worst_performer={},
            average_return=0.0,
            period_days=period_days,
            summary_data=[],
            timestamp=datetime.now(timezone.utc)
        )
    
    # Encontrar mejores y peores performers
    return_key = f"return_{period_days}d"
    best_performer = max(summary_data, key=lambda x: x[return_key])
    worst_performer = min(summary_data, key=lambda x: x[return_key])
    
    # Calcular promedio
    avg_return = sum(item[return_key] for item in summary_data) / len(summary_data)
    
    return MarketSummary(
        period_name=f"{period_days}d",
        symbols_analyzed=len(summary_data),
        best_performer=best_performer,
        worst_performer=worst_performer,
        average_return=avg_return,
        period_days=period_days,
        summary_data=summary_data,
        timestamp=datetime.now(timezone.utc)
    )


def generate_weekly_summary(current_data: Dict[str, pd.Series]) -> Optional[MarketSummary]:
    """
    Genera un resumen semanal del mercado.
    
    Args:
        current_data: Datos actuales por símbolo
    
    Returns:
        MarketSummary con el resumen semanal o None si no hay datos
    """
    market_summary = analyze_market_performance(current_data, period_days=20)
    
    if market_summary.symbols_analyzed == 0:
        return None
    
    return market_summary


def send_weekly_summary(settings: Settings, current_data: dict[str, pd.Series]) -> bool:
    """
    Genera y envía resumen semanal si está habilitado.
    
    Args:
        settings: Configuración del sistema
        current_data: Datos de mercado actuales
    
    Returns:
        bool: True si se envió correctamente, False si no
    """
    if not settings.alerts.weekly_summary.enabled:
        return False
    
    notifier = build_notifier(settings)
    weekly_summary = generate_weekly_summary(current_data)
    if not weekly_summary:
        return False
    
    # Enviar notificación
    notification_sent = False
    if notifier:
        notification_sent = notifier.send_summary(weekly_summary)
    
    return notification_sent or notifier is None