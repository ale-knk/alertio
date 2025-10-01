# src/alertio/alerts.py
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

from alertio.config import Settings
from alertio.summaries import generate_weekly_summary
from alertio.types import AlertType
from alertio.sqlite import SQLiteStore
from alertio.cooldown import create_cooldown_manager
from alertio.telegram import build_notifier

@dataclass
class Alert:
    """Alerta financiera con información completa para notificación"""
    symbol: str
    rule_key: str
    message: str
    price: float
    alert_type: AlertType
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)  # Datos adicionales


def scan_for_alerts(symbol: str, row: pd.Series, *,
                    return_thresholds: Dict[int, Dict[str, float]]) -> List[Alert]:
    """
    Escanea datos de un símbolo buscando condiciones que requieran alertas.
    Genera UNA SOLA alerta por símbolo que combina información de todas las ventanas.
    
    Args:
        symbol: Símbolo del activo
        row: Serie con datos del activo (debe incluir columnas 'close' y 'return_Nd')
        return_thresholds: Dict con ventanas y umbrales, ej:
            {5: {'min': -0.10, 'max': 0.15}, 10: {'min': -0.15, 'max': 0.20}}
    
    Returns:
        Lista con máximo 1 Alert por símbolo (vacía si no hay condiciones)
    """
    alerts: List[Alert] = []
    price = float(row["close"])
    timestamp = datetime.utcnow()
    
    # Recopilar información contextual de todas las ventanas disponibles
    context_returns = {}
    for col in row.index:
        if col.startswith('return_') and col != 'close':
            try:
                window_days = int(col.replace('return_', '').replace('d', ''))
                context_returns[window_days] = float(row[col])
            except (ValueError, TypeError):
                continue

    # Analizar todas las ventanas y recopilar violaciones de umbrales
    violated_windows = []
    overall_trend = 0  # Positivo = subida, Negativo = caída
    
    for window, thresholds in return_thresholds.items():
        return_col = f"return_{window}d"
        if return_col not in row.index:
            continue
            
        return_value = float(row[return_col])
        
        # Verificar umbral mínimo (caídas)
        if 'min' in thresholds and return_value <= thresholds['min']:
            violated_windows.append({
                'window': window,
                'return_value': return_value,
                'threshold': thresholds['min'],
                'threshold_type': 'min',
                'severity': abs(return_value - thresholds['min']) / abs(thresholds['min'])
            })
            overall_trend -= 1  # Contribuye a tendencia bajista
        
        # Verificar umbral máximo (subidas)
        if 'max' in thresholds and return_value >= thresholds['max']:
            violated_windows.append({
                'window': window,
                'return_value': return_value,
                'threshold': thresholds['max'],
                'threshold_type': 'max',
                'severity': abs(return_value - thresholds['max']) / abs(thresholds['max'])
            })
            overall_trend += 1  # Contribuye a tendencia alcista
    
    # Si no hay violaciones, no generar alerta
    if not violated_windows:
        return alerts
    
    # Determinar tipo de alerta basado en tendencia general
    alert_type = AlertType.DROP if overall_trend < 0 else AlertType.RISE
    
    # Crear mensaje consolidado
    if alert_type == AlertType.DROP:
        msg_parts = ["📉 CAÍDAS DETECTADAS:"]
        for vw in violated_windows:
            if vw['threshold_type'] == 'min':
                msg_parts.append(f"  • {vw['window']}d: {vw['return_value']:.1%} (umbral: {vw['threshold']:.1%})")
    else:
        msg_parts = ["📈 SUBIDAS DETECTADAS:"]
        for vw in violated_windows:
            if vw['threshold_type'] == 'max':
                msg_parts.append(f"  • {vw['window']}d: {vw['return_value']:.1%} (umbral: {vw['threshold']:.1%})")
    
    consolidated_message = "\n".join(msg_parts)
    
    # Crear rule_key único para el símbolo (no por ventana)
    rule_key = f"symbol_{symbol}_{alert_type.value}"
    
    # Metadata enriquecida con todas las ventanas violadas
    metadata = {
        'violated_windows': violated_windows,
        'context_returns': context_returns,
        'price': price,
        'symbol': symbol,
        'overall_trend': overall_trend,
        'total_violations': len(violated_windows),
        'max_severity': max((vw['severity'] for vw in violated_windows), default=0)
    }
    
    # Crear UNA SOLA alerta consolidada
    alerts.append(Alert(
        symbol=symbol,
        rule_key=rule_key,
        message=consolidated_message,
        price=price,
        alert_type=alert_type,
        timestamp=timestamp,
        metadata=metadata
    ))

    return alerts



def prepare_alerts(settings: Settings, current_data: dict[str, pd.Series]) -> List[Alert]:
    """Prepara alertas basadas en umbrales de retornos configurados"""
    alerts: List[Alert] = []
    
    # Convertir thresholds a formato dict para evaluate_row
    return_thresholds = {}
    for threshold_config in settings.returns.thresholds:
        window = threshold_config.window
        thresholds = {}
        if threshold_config.min_threshold is not None:
            thresholds['min'] = threshold_config.min_threshold
        if threshold_config.max_threshold is not None:
            thresholds['max'] = threshold_config.max_threshold
        if thresholds:  # Solo agregar si hay al menos un threshold
            return_thresholds[window] = thresholds
    
    # Generar alertas de precio (caída/subida)
    for sym, row in current_data.items():
        alerts.extend(
            scan_for_alerts(
                sym,
                row,
                return_thresholds=return_thresholds,
            )
        )
    
    return alerts

def send_and_log_alerts(settings: Settings, store: SQLiteStore, alerts: List[Alert]) -> int:
    """Envía y registra alertas con cooldown inteligente"""
    notifier = build_notifier(settings)
    cooldown_manager = create_cooldown_manager(settings)
    sent = 0
    
    for alert in alerts:
        # Verificar si el tipo de alerta está habilitado
        if not _is_alert_type_enabled(settings, alert.alert_type):
            continue

        # Obtener información de cooldown
        cooldown_info = store.get_alert_cooldown_info(alert.symbol, alert.rule_key)
        
        # Calcular cooldown inteligente
        cooldown_result = cooldown_manager.calculate_cooldown(
            alert=alert,
            last_alert_time=cooldown_info["last_alert_time"],
            consecutive_alerts=cooldown_info["consecutive_alerts"]
        )
        
        # Si está en cooldown, saltar esta alerta
        if cooldown_result.is_in_cooldown:
            print(f"⏰ {alert.symbol} {alert.rule_key}: {cooldown_manager.get_cooldown_summary(alert, cooldown_info['last_alert_time'], cooldown_info['consecutive_alerts'])}")
            continue

        # Enviar notificación si está configurada
        notification_sent = False
        if notifier:
            notification_sent = notifier.send_alert(alert)
        
        # Registrar en base de datos solo si se envió correctamente o no hay notificador
        if notification_sent or notifier is None:
            # Log the alert to database
            store.insert_alert(
                symbol=alert.symbol, 
                rule_key=alert.rule_key, 
                price=alert.price, 
                message=alert.message,
                alert_type=alert.alert_type.value,
                metadata=alert.metadata
            )
            sent += 1
            print(f"✅ {alert.symbol} {alert.rule_key}: Alerta enviada (cooldown: {cooldown_result.cooldown_days:.1f}d)")
        
    return sent


def _is_alert_type_enabled(settings: Settings, alert_type: AlertType) -> bool:
    """Verifica si un tipo de alerta está habilitado"""
    if alert_type == AlertType.DROP:
        return settings.alerts.drop_alerts.enabled
    elif alert_type == AlertType.RISE:
        return settings.alerts.rise_alerts.enabled
    else:
        return True


