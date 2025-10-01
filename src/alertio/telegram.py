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
                except Exception:
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
        """Formatea alertas de precio (caída/subida) con información consolidada de todas las ventanas"""
        time_str = alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')
        
        # Emojis según el tipo de alerta
        direction_emoji = "📉" if alert.alert_type.value == "drop" else "📈"
        trend_emoji = "🔴" if alert.alert_type.value == "drop" else "🟢"
        
        # Obtener información de ventanas violadas
        violated_windows = alert.metadata.get('violated_windows', [])
        total_violations = alert.metadata.get('total_violations', 0)
        
        # Formatear mensaje principal simplificado
        message = (
            f"<b>{title}</b>\n"
            f"{'=' * 30}\n\n"
            
            # Información principal
            f"{direction_emoji} <b>ALERTA DETECTADA</b>\n"
            f"{trend_emoji} {total_violations} ventana(s) violada(s)\n\n"
            
            # Precio actual
            f"💰 <b>Precio:</b> ${alert.price:.2f}\n\n"
            
            # Rendimientos por ventana (simplificado)
            f"📊 <b>Rendimientos por ventana:</b>\n"
            f"{self._format_simple_returns(alert.metadata.get('context_returns', {}), violated_windows)}\n\n"
            
            # Timestamp
            f"🕒 {time_str}"
        )
        
        return message
    
    def _format_simple_returns(self, context_returns: dict, violated_windows: list) -> str:
        """Formatea los rendimientos de forma simple, destacando las ventanas violadas"""
        if not context_returns:
            return "   Sin datos disponibles"
        
        # Obtener ventanas violadas para destacarlas
        violated_window_days = {vw['window'] for vw in violated_windows}
        
        # Ordenar ventanas por días
        sorted_returns = sorted(context_returns.items())
        
        # Formatear cada ventana
        lines = []
        for window_days, return_value in sorted_returns:
            emoji = "📈" if return_value >= 0 else "📉"
            
            # Destacar ventanas violadas con emoji de alerta
            if window_days in violated_window_days:
                emoji = "🚨"  # Alerta para ventanas violadas
            
            lines.append(f"   {emoji} {window_days}d: {return_value:+.1%}")
        
        return "\n".join(lines) if lines else "   Sin ventanas disponibles"
    
    def _get_market_insights(self, market_summary) -> dict:
        """Obtiene insights del mercado basados en el resumen"""
        if not market_summary.summary_data:
            return {
                'market_mood': '🟡 Sin datos',
                'positive_symbols': 0,
                'negative_symbols': 0,
                'bullish_ratio': 0.0,
                'volatility': 0.0
            }
        
        return_key = f'return_{market_summary.period_days}d'
        
        # Calcular volatilidad (diferencia entre mejor y peor performer)
        best_return = market_summary.best_performer.get(return_key, 0)
        worst_return = market_summary.worst_performer.get(return_key, 0)
        volatility = best_return - worst_return
        
        # Determinar tendencia general del mercado
        positive_count = sum(1 for item in market_summary.summary_data if item.get(return_key, 0) > 0)
        total_count = len(market_summary.summary_data)
        bullish_ratio = positive_count / total_count if total_count > 0 else 0
        
        if bullish_ratio > 0.7:
            market_mood = "🟢 Alcista"
        elif bullish_ratio < 0.3:
            market_mood = "🔴 Bajista"
        else:
            market_mood = "🟡 Mixto"
        
        return {
            'market_mood': market_mood,
            'positive_symbols': positive_count,
            'negative_symbols': total_count - positive_count,
            'bullish_ratio': bullish_ratio,
            'volatility': volatility
        }
    
    def _format_performance_categories(self, market_summary, return_key: str) -> str:
        """Formatea las categorías de rendimiento"""
        if not market_summary.summary_data:
            return ""
        
        # Categorizar símbolos por tendencia (alcistas vs bajistas)
        bullish = []    # > 0% (alcistas)
        bearish = []    # <= 0% (bajistas)
        
        for data in market_summary.summary_data:
            return_value = data.get(return_key, 0)
            if return_value > 0:
                bullish.append(data)
            else:
                bearish.append(data)
        
        # Ordenar cada categoría por rendimiento
        bullish.sort(key=lambda x: x.get(return_key, 0), reverse=True)  # Alcistas: mayor primero
        bearish.sort(key=lambda x: x.get(return_key, 0), reverse=False)  # Bajistas: menor primero (más negativo primero)
        
        message = "<b>📊 Distribución por tendencia:</b>\n"
        
        if bullish:
            message += f"   📈 <b>Alcistas ({len(bullish)} símbolos):</b>\n"
            for data in bullish[:5]:  # Mostrar hasta 5 alcistas
                emoji = "🚀" if data.get(return_key, 0) > 10 else "📈"
                message += f"      {emoji} {data['symbol']}: {data[return_key]:+.1f}%\n"
            if len(bullish) > 5:
                message += f"      • ... y {len(bullish) - 5} más\n"
            message += "\n"
        else:
            message += "   📈 <b>Alcistas (0 símbolos):</b>\n"
            message += "      Sin símbolos alcistas\n\n"
        
        if bearish:
            message += f"   📉 <b>Bajistas ({len(bearish)} símbolos):</b>\n"
            for data in bearish[:5]:  # Mostrar hasta 5 bajistas
                emoji = "🔻" if data.get(return_key, 0) < -10 else "📉"
                message += f"      {emoji} {data['symbol']}: {data[return_key]:+.1f}%\n"
            if len(bearish) > 5:
                message += f"      • ... y {len(bearish) - 5} más\n"
            message += "\n"
        else:
            message += "   📉 <b>Bajistas (0 símbolos):</b>\n"
            message += "      Sin símbolos bajistas\n\n"
        
        return message
    
    def _format_top_performers(self, market_summary, return_key: str) -> str:
        """Formatea los top performers: 2 mejores en crecimiento y 2 mejores en caída"""
        if not market_summary.summary_data:
            return "   Sin datos disponibles"
        
        # Ordenar por rendimiento descendente
        sorted_data = sorted(market_summary.summary_data, key=lambda x: x.get(return_key, 0), reverse=True)
        
        # Separar en positivos y negativos
        positive_data = [item for item in sorted_data if item.get(return_key, 0) > 0]
        negative_data = [item for item in sorted_data if item.get(return_key, 0) <= 0]
        
        message = ""
        
        # 2 mejores en crecimiento
        if positive_data:
            message += "   📈 <b>Mejores en crecimiento:</b>\n"
            for i, data in enumerate(positive_data[:2]):
                medal = "🥇" if i == 0 else "🥈"
                message += f"      {medal} {data['symbol']}: <b>{data.get(return_key, 0):+.1f}%</b>\n"
        else:
            message += "   📈 <b>Mejores en crecimiento:</b>\n"
            message += "      Sin símbolos positivos\n"
        
        message += "\n"
        
        # 2 mejores en caída (menos negativos)
        if negative_data:
            message += "   📉 <b>Mejores en caída:</b>\n"
            for i, data in enumerate(negative_data[:2]):
                medal = "🥉" if i == 0 else "🏅"
                message += f"      {medal} {data['symbol']}: <b>{data.get(return_key, 0):+.1f}%</b>\n"
        else:
            message += "   📉 <b>Mejores en caída:</b>\n"
            message += "      Sin símbolos negativos\n"
        
        return message
    
    def _format_market_summary(self, market_summary) -> str:
        """Formatea resumen de mercado usando MarketSummary con formato mejorado"""
        time_str = market_summary.timestamp.strftime('%Y-%m-%d %H:%M UTC')
        
        # Título según el tipo de período
        if market_summary.period_name.startswith("weekly") or market_summary.period_days == 7:
            title = "📊 RESUMEN SEMANAL DEL MERCADO"
        elif market_summary.period_name.startswith("monthly") or market_summary.period_days >= 20:
            title = "📊 RESUMEN MENSUAL DEL MERCADO"
        else:
            title = f"📊 RESUMEN DEL MERCADO ({market_summary.period_days}d)"
        
        # Obtener insights del mercado
        insights = self._get_market_insights(market_summary)
        
        best = market_summary.best_performer
        worst = market_summary.worst_performer
        return_key = f'return_{market_summary.period_days}d'
        
        message = (
            f"<b>{title}</b>\n"
            f"{'=' * 40}\n\n"
            
            # Resumen general
            f"📊 <b>Análisis de {market_summary.symbols_analyzed} símbolos</b>\n"
            f"📈 <b>Retorno promedio:</b> {market_summary.average_return:+.1f}%\n"
            f"🎯 <b>Estado del mercado:</b> {insights['market_mood']}\n\n"
            
            # Top performers - 2 mejores en crecimiento y 2 mejores en caída
            f"🏆 <b>TOP PERFORMERS ({market_summary.period_days}d):</b>\n"
            f"{self._format_top_performers(market_summary, return_key)}\n"
            
            # Estadísticas del mercado
            f"📊 <b>Estadísticas del mercado:</b>\n"
            f"   • Símbolos positivos: {insights['positive_symbols']}/{market_summary.symbols_analyzed} ({insights['bullish_ratio']:.0%})\n"
            f"   • Volatilidad: {insights['volatility']:.1f}% (rango: {worst.get(return_key, 0):.1f}% a {best.get(return_key, 0):.1f}%)\n\n"
        )
        
        # Agregar categorías de rendimiento
        message += self._format_performance_categories(market_summary, return_key)
        
        # Agregar detalle de todos los símbolos si hay pocos
        if len(market_summary.summary_data) <= 10:  # Solo mostrar detalle si hay pocos símbolos
            message += "<b>📋 Detalle por símbolo:</b>\n"
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