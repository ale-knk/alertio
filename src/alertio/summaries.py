# src/alertio/summaries.py
"""
Módulo para generar resúmenes de mercado.
Este módulo se enfoca en análisis general de mercado, no en alertas específicas.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd



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


def generate_monthly_summary(current_data: Dict[str, pd.Series]) -> Optional[MarketSummary]:
    """
    Genera un resumen mensual del mercado (usando datos de 20 días).
    
    Args:
        current_data: Datos actuales por símbolo
    
    Returns:
        MarketSummary con el resumen mensual o None si no hay datos
    """
    market_summary = analyze_market_performance(current_data, period_days=20)
    
    if market_summary.symbols_analyzed == 0:
        return None
    
    # Modificar el period_name para indicar que es mensual
    market_summary.period_name = "monthly"
    
    return market_summary


def _format_weekly_message(summary: MarketSummary) -> str:
    """Formatea el mensaje para resumen semanal."""
    best = summary.best_performer
    worst = summary.worst_performer
    
    return (
        f"Resumen semanal de {summary.symbols_analyzed} símbolos:\n"
        f"📈 Mejor: {best['symbol']} (+{best[f'return_{summary.period_days}d']:.1f}%)\n"
        f"📉 Peor: {worst['symbol']} ({worst[f'return_{summary.period_days}d']:.1f}%)\n"
        f"📊 Promedio {summary.period_days}d: {summary.average_return:.1f}%"
    )


def _format_monthly_message(summary: MarketSummary) -> str:
    """Formatea el mensaje para resumen mensual."""
    best = summary.best_performer
    worst = summary.worst_performer
    
    return (
        f"Resumen mensual de {summary.symbols_analyzed} símbolos:\n"
        f"📈 Mejor: {best['symbol']} (+{best[f'return_{summary.period_days}d']:.1f}%)\n"
        f"📉 Peor: {worst['symbol']} ({worst[f'return_{summary.period_days}d']:.1f}%)\n"
        f"📊 Promedio mensual: {summary.average_return:.1f}%"
    )


def get_market_insights(current_data: Dict[str, pd.Series]) -> Dict[str, Any]:
    """
    Genera insights adicionales del mercado.
    
    Returns:
        Diccionario con insights como volatilidad, tendencias, etc.
    """
    summary = analyze_market_performance(current_data)
    
    if summary.symbols_analyzed == 0:
        return {}
    
    # Calcular volatilidad (diferencia entre mejor y peor performer)
    volatility = summary.best_performer[f'return_{summary.period_days}d'] - summary.worst_performer[f'return_{summary.period_days}d']
    
    # Determinar tendencia general del mercado
    positive_count = sum(1 for item in summary.summary_data if item[f'return_{summary.period_days}d'] > 0)
    total_count = len(summary.summary_data)
    bullish_ratio = positive_count / total_count if total_count > 0 else 0
    
    if bullish_ratio > 0.7:
        market_mood = "🟢 Alcista"
    elif bullish_ratio < 0.3:
        market_mood = "🔴 Bajista"
    else:
        market_mood = "🟡 Mixto"
    
    return {
        'volatility': volatility,
        'bullish_ratio': bullish_ratio,
        'market_mood': market_mood,
        'positive_symbols': positive_count,
        'negative_symbols': total_count - positive_count,
        'avg_return': summary.average_return
    }
