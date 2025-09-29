# src/alertio/telegram.py
from __future__ import annotations
import requests
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class TelegramNotifier:
    """Notificador de Telegram mejorado con manejo de errores y logging"""
    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"
    timeout: int = 15
    
    def __post_init__(self):
        """Validar configuración al crear la instancia"""
        if not self.bot_token or len(self.bot_token) < 10:
            raise ValueError("bot_token inválido")
        if not self.chat_id:
            raise ValueError("chat_id requerido")
    
    def send(self, text: str, disable_web_page_preview: bool = True) -> bool:
        """
        Envía un mensaje de texto a Telegram.
        
        Returns:
            bool: True si se envió correctamente, False si hubo error
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            }
            
            logger.debug(f"Enviando mensaje a Telegram: {len(text)} caracteres")
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info("Mensaje enviado exitosamente a Telegram")
            return True
            
        except requests.exceptions.Timeout:
            logger.error("Timeout al enviar mensaje a Telegram")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP al enviar a Telegram: {e}")
            if hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    logger.error(f"Detalle del error: {error_data}")
                except:
                    pass
            return False
        except Exception as e:
            logger.error(f"Error inesperado al enviar a Telegram: {e}")
            return False
    

    def send_alert(self, alert) -> bool:
        """
        Envía una alerta de precio (caída/subida).
        
        Args:
            alert: Instancia de Alert con alert_type DROP o RISE
        """
        from alertio.types import format_alert_title, get_alert_config
        
        config = get_alert_config(alert.alert_type)
        title = format_alert_title(alert.alert_type, alert.symbol)
        
        formatted_message = self._format_price_alert(alert, title, config)
        return self.send(formatted_message)
    
    def send_summary(self, market_summary) -> bool:
        """
        Envía un resumen de mercado.
        
        Args:
            market_summary: Instancia de MarketSummary
        """
        formatted_message = self._format_market_summary(market_summary)
        return self.send(formatted_message)
    
    
    def _format_price_alert(self, alert, title: str, config) -> str:
        """Formatea alertas de precio (caída/subida)"""
        time_str = alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')
        
        # Información adicional del metadata
        window = alert.metadata.get('window', 'N/A')
        actual_return = alert.metadata.get('actual_return', 0)
        threshold = alert.metadata.get('threshold', 0)
        
        return (
            f"<b>{title}</b>\n\n"
            f"💬 {alert.message}\n"
            f"💰 Precio: <b>${alert.price:.2f}</b>\n"
            f"📊 Ventana: {window} días\n"
            f"📈 Retorno real: <b>{actual_return:.2%}</b>\n"
            f"🎯 Umbral: {threshold:.2%}\n"
            f"🕒 {time_str}"
        )
    
    def _format_market_summary(self, market_summary) -> str:
        """Formatea resumen de mercado usando MarketSummary"""
        time_str = market_summary.timestamp.strftime('%Y-%m-%d %H:%M UTC')
        
        # Título según el tipo de período
        if market_summary.period_name.startswith("weekly") or market_summary.period_days == 7:
            title = "📊 RESUMEN SEMANAL DEL MERCADO"
        elif market_summary.period_name.startswith("monthly") or market_summary.period_days >= 20:
            title = "📊 RESUMEN MENSUAL DEL MERCADO"
        else:
            title = f"📊 RESUMEN DEL MERCADO ({market_summary.period_days}d)"
        
        best = market_summary.best_performer
        worst = market_summary.worst_performer
        
        message = (
            f"<b>{title}</b>\n\n"
            f"📊 <b>Análisis de {market_summary.symbols_analyzed} símbolos</b>\n\n"
            f"🏆 <b>Mejor performer ({market_summary.period_days}d):</b>\n"
            f"   {best.get('symbol', 'N/A')}: <b>+{best.get(f'return_{market_summary.period_days}d', 0):.1f}%</b>\n\n"
            f"📉 <b>Peor performer ({market_summary.period_days}d):</b>\n"
            f"   {worst.get('symbol', 'N/A')}: <b>{worst.get(f'return_{market_summary.period_days}d', 0):.1f}%</b>\n\n"
            f"📈 <b>Retorno promedio:</b> {market_summary.average_return:.1f}%\n\n"
        )
        
        # Agregar detalle de todos los símbolos si hay pocos
        if len(market_summary.summary_data) <= 8:  # Solo mostrar detalle si hay pocos símbolos
            message += "<b>📋 Detalle por símbolo:</b>\n"
            return_key = f'return_{market_summary.period_days}d'
            for data in sorted(market_summary.summary_data, key=lambda x: x[return_key], reverse=True):
                emoji = "📈" if data[return_key] >= 0 else "📉"
                message += f"{emoji} {data['symbol']}: {data[return_key]:+.1f}%\n"
            message += "\n"
        
        message += f"🕒 {time_str}"
        
        return message
    
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión enviando un mensaje de test.
        
        Returns:
            bool: True si la conexión funciona
        """
        test_message = (
            "🤖 <b>Test de Conexión</b>\n\n"
            "✅ Bot de Alertio funcionando correctamente\n"
            f"🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        
        return self.send(test_message)
    
    def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del bot.
        
        Returns:
            Dict con información del bot o None si hay error
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            if data.get("ok"):
                return data.get("result", {})
            else:
                logger.error(f"Error API Telegram: {data.get('description')}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo info del bot: {e}")
            return None