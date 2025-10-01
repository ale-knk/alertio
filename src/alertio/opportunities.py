"""
Módulo para análisis de oportunidades de entrada.
Este módulo se enfoca en identificar activos con caídas significativas que podrían representar oportunidades de entrada.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd


@dataclass
class Opportunity:
    """Oportunidad de entrada identificada para un activo."""
    symbol: str
    price: float
    returns: Dict[int, float]  # {window_days: return_percentage}
    opportunity_score: float  # Puntuación de 0-100
    severity: str  # "low", "medium", "high"
    windows_with_drops: List[int]  # Ventanas que muestran caídas
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OpportunitySummary:
    """Resumen de oportunidades de entrada encontradas."""
    total_analyzed: int
    opportunities_found: int
    opportunities: List[Opportunity]
    average_drop: float
    best_opportunity: Optional[Opportunity]
    timestamp: datetime
    analysis_windows: List[int]


def analyze_opportunities(
    current_data: Dict[str, pd.Series], 
    analysis_windows: List[int] = [5, 10, 20],
    min_drop_threshold: float = -0.05,  # -5% mínimo
    min_windows_required: int = 1
) -> OpportunitySummary:
    """
    Analiza oportunidades de entrada basadas en caídas de precio.
    
    Args:
        current_data: Datos actuales por símbolo
        analysis_windows: Ventanas de tiempo a analizar en días
        min_drop_threshold: Caída mínima para considerar oportunidad (ej. -0.05 = -5%)
        min_windows_required: Mínimo de ventanas que deben mostrar caídas
    
    Returns:
        OpportunitySummary con las oportunidades encontradas
    """
    opportunities = []
    total_analyzed = 0
    
    for symbol, row in current_data.items():
        # Saltar índices para análisis individual
        if symbol.startswith("^"):
            continue
            
        total_analyzed += 1
        
        # Analizar retornos en las ventanas especificadas
        symbol_returns = {}
        windows_with_drops = []
        
        for window in analysis_windows:
            return_col = f"return_{window}d"
            if return_col in row.index:
                return_value = float(row[return_col])
                symbol_returns[window] = return_value
                
                # Verificar si es una caída significativa
                if return_value <= min_drop_threshold:
                    windows_with_drops.append(window)
        
        # Solo considerar si cumple el mínimo de ventanas requeridas
        if len(windows_with_drops) >= min_windows_required:
            # Calcular puntuación de oportunidad
            opportunity_score = _calculate_opportunity_score(
                symbol_returns, windows_with_drops, min_drop_threshold
            )
            
            # Determinar severidad
            severity = _determine_severity(opportunity_score, len(windows_with_drops))
            
            # Obtener precio actual
            price = float(row.get('close', row.get('Close', 0)))
            
            opportunity = Opportunity(
                symbol=symbol,
                price=price,
                returns=symbol_returns,
                opportunity_score=opportunity_score,
                severity=severity,
                windows_with_drops=windows_with_drops,
                metadata={
                    'alias': _get_symbol_alias(symbol),
                    'analysis_timestamp': datetime.now(timezone.utc)
                }
            )
            opportunities.append(opportunity)
    
    # Ordenar por puntuación de oportunidad (mayor puntuación = mejor oportunidad)
    opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)
    
    # Calcular estadísticas
    avg_drop = 0.0
    if opportunities:
        avg_drop = sum(
            sum(opp.returns[window] for window in opp.windows_with_drops) / len(opp.windows_with_drops)
            for opp in opportunities
        ) / len(opportunities)
    
    return OpportunitySummary(
        total_analyzed=total_analyzed,
        opportunities_found=len(opportunities),
        opportunities=opportunities,
        average_drop=avg_drop,
        best_opportunity=opportunities[0] if opportunities else None,
        timestamp=datetime.now(timezone.utc),
        analysis_windows=analysis_windows
    )


def _calculate_opportunity_score(
    returns: Dict[int, float], 
    windows_with_drops: List[int], 
    min_threshold: float
) -> float:
    """
    Calcula una puntuación de oportunidad de 0-100.
    Mayor puntuación = mejor oportunidad.
    """
    if not windows_with_drops:
        return 0.0
    
    # Factor 1: Magnitud de las caídas (más caída = mayor puntuación)
    magnitude_score = 0.0
    for window in windows_with_drops:
        if window in returns:
            # Convertir a positivo y escalar (ej. -0.15 = 15 puntos)
            drop_magnitude = abs(returns[window])
            magnitude_score += drop_magnitude * 100
    
    # Factor 2: Consistencia (más ventanas con caídas = mayor puntuación)
    consistency_score = len(windows_with_drops) * 10
    
    # Factor 3: Severidad relativa al umbral
    severity_score = 0.0
    for window in windows_with_drops:
        if window in returns:
            # Qué tan por debajo del umbral está
            excess_drop = abs(returns[window] - min_threshold)
            severity_score += excess_drop * 50
    
    # Combinar factores (pesos: 60% magnitud, 25% consistencia, 15% severidad)
    total_score = (magnitude_score * 0.6) + (consistency_score * 0.25) + (severity_score * 0.15)
    
    # Limitar a 0-100
    return min(max(total_score, 0.0), 100.0)


def _determine_severity(score: float, windows_count: int) -> str:
    """Determina la severidad de la oportunidad."""
    if score >= 70 or windows_count >= 3:
        return "high"
    elif score >= 40 or windows_count >= 2:
        return "medium"
    else:
        return "low"


def _get_symbol_alias(symbol: str) -> str:
    """Obtiene un alias legible para el símbolo."""
    # Mapeo básico de símbolos comunes
    aliases = {
        "AAPL": "Apple Inc.",
        "GOOGL": "Alphabet Inc.",
        "MSFT": "Microsoft Corp.",
        "NVDA": "NVIDIA Corp.",
        "AMZN": "Amazon.com Inc.",
        "TSLA": "Tesla Inc.",
        "META": "Meta Platforms Inc.",
        "SPY": "S&P 500 ETF",
        "QQQ": "NASDAQ-100 ETF",
        "IWM": "Russell 2000 ETF",
    }
    return aliases.get(symbol, symbol)


def format_opportunity_message(summary: OpportunitySummary) -> str:
    """Formatea el mensaje de oportunidades para Telegram."""
    if summary.opportunities_found == 0:
        return "🎯 ANÁLISIS DE OPORTUNIDADES\n\nNo se encontraron oportunidades de entrada significativas en este momento."
    
    # Encabezado
    message_parts = [
        f"🎯 OPORTUNIDADES DE ENTRADA - {summary.timestamp.strftime('%d/%m/%Y %H:%M')}",
        "",
        f"📊 Análisis: {summary.total_analyzed} activos | {summary.opportunities_found} oportunidades",
        f"📉 Caída promedio: {summary.average_drop:.1%}",
        ""
    ]
    
    # Top oportunidades (máximo 10)
    top_opportunities = summary.opportunities[:10]
    
    message_parts.append("🏆 TOP OPORTUNIDADES:")
    
    for i, opp in enumerate(top_opportunities, 1):
        # Emoji según severidad
        severity_emoji = {"high": "🥇", "medium": "🥈", "low": "🥉"}
        emoji = severity_emoji.get(opp.severity, "📊")
        
        # Formatear retornos
        returns_text = []
        for window in sorted(opp.windows_with_drops):
            if window in opp.returns:
                returns_text.append(f"{opp.returns[window]:.1%}")
        
        returns_str = ", ".join(returns_text)
        
        # Línea de oportunidad
        opp_line = f"{emoji} {opp.symbol}: {returns_str} (Score: {opp.opportunity_score:.0f})"
        message_parts.append(opp_line)
    
    # Resumen final
    if summary.opportunities_found > 10:
        message_parts.append(f"\n... y {summary.opportunities_found - 10} oportunidades más")
    
    message_parts.append(f"\n💡 Ventanas analizadas: {', '.join(map(str, summary.analysis_windows))}d")
    
    return "\n".join(message_parts)


def generate_opportunity_summary(current_data: Dict[str, pd.Series]) -> Optional[OpportunitySummary]:
    """
    Genera un resumen de oportunidades de entrada.
    
    Args:
        current_data: Datos actuales por símbolo
    
    Returns:
        OpportunitySummary con las oportunidades encontradas o None si no hay datos
    """
    summary = analyze_opportunities(
        current_data, 
        analysis_windows=[5, 10, 20],
        min_drop_threshold=-0.05,  # -5%
        min_windows_required=1
    )
    
    if summary.opportunities_found == 0:
        return None
    
    return summary
