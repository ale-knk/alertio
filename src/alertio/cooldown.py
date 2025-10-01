# src/alertio/cooldown.py
"""
Sistema de cooldown inteligente para alertas.
Implementa cooldowns por magnitud, ventana de tiempo y progresivo.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone, timedelta

from alertio.config import CooldownConfig


@dataclass
class CooldownResult:
    """Resultado del cálculo de cooldown"""
    is_in_cooldown: bool
    cooldown_days: float
    reason: str  # Explicación del cooldown aplicado
    last_alert_time: Optional[datetime] = None
    consecutive_alerts: int = 0


class SmartCooldownManager:
    """Gestor de cooldown inteligente para alertas"""
    
    def __init__(self, config: CooldownConfig):
        self.config = config
    
    def calculate_cooldown(self, alert, last_alert_time: Optional[datetime], 
                          consecutive_alerts: int = 0) -> CooldownResult:
        """
        Calcula el cooldown inteligente para una alerta.
        
        Args:
            alert: Instancia de Alert
            last_alert_time: Última vez que se disparó esta alerta
            consecutive_alerts: Número de alertas consecutivas para este símbolo+regla
        
        Returns:
            CooldownResult con el resultado del cálculo
        """
        # Si no hay alerta previa, no hay cooldown
        if last_alert_time is None:
            return CooldownResult(
                is_in_cooldown=False,
                cooldown_days=0,
                reason="Primera alerta para este símbolo+regla",
                last_alert_time=None,
                consecutive_alerts=0
            )
        
        # Calcular cooldown por magnitud
        magnitude_cooldown = self._get_magnitude_cooldown(alert)
        
        # Calcular cooldown por ventana de tiempo
        window_cooldown = self._get_window_cooldown(alert)
        
        # Calcular cooldown progresivo
        progressive_multiplier = self._get_progressive_multiplier(consecutive_alerts, alert)
        
        # Usar el mayor de los cooldowns base
        base_cooldown = max(magnitude_cooldown, window_cooldown)
        
        # Aplicar multiplicador progresivo
        final_cooldown = base_cooldown * progressive_multiplier
        
        # Verificar si está en cooldown
        if last_alert_time is not None:
            time_since_last = datetime.now(timezone.utc) - last_alert_time
            is_in_cooldown = time_since_last < timedelta(days=final_cooldown)
        else:
            is_in_cooldown = False
        
        # Generar explicación
        reason_parts = []
        if magnitude_cooldown >= window_cooldown:
            reason_parts.append(f"cooldown por magnitud ({self._get_magnitude_category(alert)}: {magnitude_cooldown}d)")
        else:
            violated_windows = alert.metadata.get('violated_windows', [])
            if violated_windows:
                min_window = min(vw['window'] for vw in violated_windows)
                reason_parts.append(f"cooldown por ventana ({min_window}d: {window_cooldown:.1f}d)")
            else:
                reason_parts.append(f"cooldown base ({window_cooldown:.1f}d)")
        
        if progressive_multiplier > 1:
            reason_parts.append(f"multiplicador progresivo x{progressive_multiplier:.1f} ({consecutive_alerts} alertas consecutivas)")
        
        reason = " + ".join(reason_parts)
        
        return CooldownResult(
            is_in_cooldown=is_in_cooldown,
            cooldown_days=final_cooldown,
            reason=reason,
            last_alert_time=last_alert_time,
            consecutive_alerts=consecutive_alerts
        )
    
    def _get_magnitude_cooldown(self, alert) -> int:
        """Calcula cooldown basado en la magnitud del movimiento (adaptado para alertas consolidadas)"""
        # Para alertas consolidadas, usar la severidad máxima de todas las ventanas violadas
        max_severity = alert.metadata.get('max_severity', 0)
        total_violations = alert.metadata.get('total_violations', 0)
        
        # Si hay muchas violaciones, aumentar la magnitud percibida
        magnitude_factor = 1.0 + (total_violations - 1) * 0.2  # +20% por violación adicional
        adjusted_magnitude = max_severity * magnitude_factor
        
        if adjusted_magnitude < 0.05:  # < 5%
            return self.config.magnitude_cooldowns.get("small", 1)
        elif adjusted_magnitude < 0.15:  # 5-15%
            return self.config.magnitude_cooldowns.get("medium", 3)
        else:  # > 15%
            return self.config.magnitude_cooldowns.get("large", 7)
    
    def _get_window_cooldown(self, alert) -> float:
        """Calcula cooldown basado en las ventanas de tiempo violadas (adaptado para alertas consolidadas)"""
        violated_windows = alert.metadata.get('violated_windows', [])
        
        if not violated_windows:
            return self.config.base_days
        
        # Usar la ventana más corta violada (más sensible) como base
        min_window = min(vw['window'] for vw in violated_windows)
        base_cooldown = self.config.window_cooldowns.get(min_window, self.config.base_days)
        
        # Ajustar por número de ventanas violadas
        violation_multiplier = 1.0 + (len(violated_windows) - 1) * 0.3  # +30% por ventana adicional
        
        return base_cooldown * violation_multiplier
    
    def _get_progressive_multiplier(self, consecutive_alerts: int, alert=None) -> float:
        """Calcula multiplicador progresivo basado en alertas consecutivas"""
        if not self.config.progressive_enabled or consecutive_alerts <= 0:
            return 1.0
        
        # NUEVO: Movimientos extremos (>20%) ignoran el progresivo para no perder alertas importantes
        if alert is not None:
            max_severity = alert.metadata.get('max_severity', 0)
            if max_severity >= 0.20:  # Movimiento extremo (20%+)
                return 1.0  # Sin multiplicador progresivo
        
        multiplier = 1.0 + (consecutive_alerts * self.config.progressive_multiplier)
        return min(multiplier, self.config.max_progressive_multiplier)
    
    def _get_magnitude_category(self, alert) -> str:
        """Obtiene la categoría de magnitud para logging (adaptado para alertas consolidadas)"""
        max_severity = alert.metadata.get('max_severity', 0)
        total_violations = alert.metadata.get('total_violations', 0)
        
        # Ajustar magnitud por número de violaciones
        magnitude_factor = 1.0 + (total_violations - 1) * 0.2
        adjusted_magnitude = max_severity * magnitude_factor
        
        if adjusted_magnitude < 0.05:
            return "pequeño"
        elif adjusted_magnitude < 0.15:
            return "mediano"
        else:
            return "grande"
    
    def get_cooldown_summary(self, alert, last_alert_time: Optional[datetime], 
                           consecutive_alerts: int = 0) -> str:
        """
        Genera un resumen legible del cooldown para logging.
        
        Returns:
            String con resumen del cooldown
        """
        result = self.calculate_cooldown(alert, last_alert_time, consecutive_alerts)
        
        if not result.is_in_cooldown:
            return f"Sin cooldown - {result.reason}"
        
        if last_alert_time is not None:
            time_remaining = timedelta(days=result.cooldown_days) - (datetime.now(timezone.utc) - last_alert_time)
            hours_remaining = time_remaining.total_seconds() / 3600
            return (f"En cooldown por {result.cooldown_days:.1f} días "
                    f"({hours_remaining:.1f}h restantes) - {result.reason}")
        else:
            return f"En cooldown por {result.cooldown_days:.1f} días - {result.reason}"


def create_cooldown_manager(settings) -> SmartCooldownManager:
    """Factory function para crear un SmartCooldownManager desde Settings"""
    return SmartCooldownManager(settings.alerts.cooldown)
