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
from alertio.telegram import TelegramNotifier


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
    
    Args:
        symbol: Símbolo del activo
        row: Serie con datos del activo (debe incluir columnas 'close' y 'return_Nd')
        return_thresholds: Dict con ventanas y umbrales, ej:
            {5: {'min': -0.10, 'max': 0.15}, 10: {'min': -0.15, 'max': 0.20}}
    
    Returns:
        Lista de Alert encontradas para este símbolo
    """
    alerts: List[Alert] = []
    price = float(row["close"])
    timestamp = datetime.utcnow()

    # Evaluar retornos por ventana de tiempo
    for window, thresholds in return_thresholds.items():
        return_col = f"return_{window}d"
        if return_col not in row.index:
            continue
            
        return_value = float(row[return_col])
        
        # Verificar umbral mínimo (caídas)
        if 'min' in thresholds and return_value <= thresholds['min']:
            msg = f"Retorno {window}d ≤ {thresholds['min']:.1%} (actual {return_value:.2%})"
            rule_key = f"return_{window}d_min_{thresholds['min']:.3f}"
            metadata = {
                'window': window,
                'threshold': thresholds['min'],
                'actual_return': return_value,
                'threshold_type': 'min'
            }
            alerts.append(Alert(
                symbol=symbol, 
                rule_key=rule_key, 
                message=msg, 
                price=price,
                alert_type=AlertType.DROP,
                timestamp=timestamp,
                metadata=metadata
            ))
        
        # Verificar umbral máximo (subidas)
        if 'max' in thresholds and return_value >= thresholds['max']:
            msg = f"Retorno {window}d ≥ {thresholds['max']:.1%} (actual {return_value:.2%})"
            rule_key = f"return_{window}d_max_{thresholds['max']:.3f}"
            metadata = {
                'window': window,
                'threshold': thresholds['max'],
                'actual_return': return_value,
                'threshold_type': 'max'
            }
            alerts.append(Alert(
                symbol=symbol,
                rule_key=rule_key,
                message=msg,
                price=price,
                alert_type=AlertType.RISE,
                timestamp=timestamp,
                metadata=metadata
            ))

    return alerts

def build_notifier(settings: Settings) -> TelegramNotifier | None:
    tg = settings.alerts.telegram
    if tg.enabled and tg.bot_token and tg.chat_id:
        return TelegramNotifier(bot_token=tg.bot_token, chat_id=tg.chat_id, parse_mode=tg.parse_mode)
    return None

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
    """Envía y registra alertas con cooldown específico por tipo"""
    notifier = build_notifier(settings)
    sent = 0
    
    for alert in alerts:
        # Determinar cooldown específico por tipo de alerta
        cooldown_days = _get_cooldown_for_alert_type(settings, alert.alert_type)
        
        # Cooldown check
        last = store.last_alert_time(alert.symbol, alert.rule_key)
        if store.is_in_cooldown(last, cooldown_days):
            continue

        # Verificar si el tipo de alerta está habilitado
        if not _is_alert_type_enabled(settings, alert.alert_type):
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
        
    return sent


def _get_cooldown_for_alert_type(settings: Settings, alert_type: AlertType) -> int:
    """Obtiene el cooldown específico para un tipo de alerta"""
    if alert_type == AlertType.DROP:
        return settings.alerts.drop_alerts.cooldown_days or settings.alerts.cooldown_days
    elif alert_type == AlertType.RISE:
        return settings.alerts.rise_alerts.cooldown_days or settings.alerts.cooldown_days
    else:
        return settings.alerts.cooldown_days


def _is_alert_type_enabled(settings: Settings, alert_type: AlertType) -> bool:
    """Verifica si un tipo de alerta está habilitado"""
    if alert_type == AlertType.DROP:
        return settings.alerts.drop_alerts.enabled
    elif alert_type == AlertType.RISE:
        return settings.alerts.rise_alerts.enabled
    else:
        return True


def send_weekly_summary(settings: Settings, current_data: dict[str, pd.Series], store = None) -> bool:
    """
    Genera y envía resumen semanal si está habilitado.
    
    Args:
        settings: Configuración del sistema
        current_data: Datos de mercado actuales
        store: Store SQLite (opcional, para logging)
    
    Returns:
        bool: True si se envió correctamente, False si no
    """
    if not settings.alerts.weekly_summary.enabled:
        return False
    
    # Verificar cooldown si hay store
    if store:
        last_summary = store.last_summary_time("weekly")
        cooldown_days = settings.alerts.weekly_summary.cooldown_days or settings.alerts.cooldown_days
        if store.is_in_cooldown(last_summary, cooldown_days):
            return False
    
    notifier = build_notifier(settings)
    weekly_summary = generate_weekly_summary(current_data)
    if not weekly_summary:
        return False
    
    # Enviar notificación
    notification_sent = False
    if notifier:
        notification_sent = notifier.send_summary(weekly_summary)
    
    # Registrar en base de datos si hay store
    if store and (notification_sent or notifier is None):
        store.insert_summary("weekly", weekly_summary, notification_sent or notifier is None)
    
    return notification_sent or notifier is None