#!/usr/bin/env python3
"""
Script de prueba para verificar las alertas consolidadas por símbolo.
Simula datos de mercado y verifica que se genere una sola alerta por símbolo.
"""

import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

# Agregar el directorio src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alertio.alerts import scan_for_alerts
from alertio.types import AlertType

def create_test_data():
    """Crea datos de prueba simulando diferentes escenarios"""
    
    # Escenario 1: AAPL con múltiples violaciones (caídas)
    aapl_data = pd.Series({
        'close': 150.0,
        'return_1d': -0.06,  # -6% (supera umbral -4%)
        'return_5d': -0.08,  # -8% (supera umbral -7%)
        'return_10d': -0.12, # -12% (supera umbral -10%)
        'return_20d': -0.05  # -5% (no supera umbral -15%)
    })
    
    # Escenario 2: GOOGL con una sola violación (subida)
    googl_data = pd.Series({
        'close': 2800.0,
        'return_1d': 0.03,   # 3% (no supera umbral 4%)
        'return_5d': 0.08,   # 8% (supera umbral 7%)
        'return_10d': 0.05,  # 5% (no supera umbral 10%)
        'return_20d': 0.12   # 12% (no supera umbral 15%)
    })
    
    # Escenario 3: MSFT sin violaciones
    msft_data = pd.Series({
        'close': 300.0,
        'return_1d': 0.02,   # 2% (no supera umbral 4%)
        'return_5d': 0.03,   # 3% (no supera umbral 7%)
        'return_10d': 0.04,  # 4% (no supera umbral 10%)
        'return_20d': 0.06   # 6% (no supera umbral 15%)
    })
    
    return {
        'AAPL': aapl_data,
        'GOOGL': googl_data,
        'MSFT': msft_data
    }

def test_consolidated_alerts():
    """Prueba la funcionalidad de alertas consolidadas"""
    
    print("🧪 Probando alertas consolidadas por símbolo...")
    print("=" * 60)
    
    # Configurar umbrales de prueba (similares a daily-prod.yaml)
    return_thresholds = {
        1: {'min': -0.04, 'max': 0.04},   # 4%
        5: {'min': -0.07, 'max': 0.07},   # 7%
        10: {'min': -0.10, 'max': 0.10},  # 10%
        20: {'min': -0.15, 'max': 0.15}   # 15%
    }
    
    # Crear datos de prueba
    test_data = create_test_data()
    
    total_alerts = 0
    
    for symbol, row in test_data.items():
        print(f"\n📊 Analizando {symbol}:")
        print(f"   Precio: ${row['close']:.2f}")
        print(f"   Retornos: 1d={row['return_1d']:+.1%}, 5d={row['return_5d']:+.1%}, 10d={row['return_10d']:+.1%}, 20d={row['return_20d']:+.1%}")
        
        # Generar alertas
        alerts = scan_for_alerts(symbol, row, return_thresholds=return_thresholds)
        
        if alerts:
            alert = alerts[0]  # Debería haber solo una alerta
            total_alerts += 1
            
            print(f"   ✅ ALERTA GENERADA:")
            print(f"      Tipo: {alert.alert_type.value.upper()}")
            print(f"      Violaciones: {alert.metadata['total_violations']}")
            print(f"      Ventanas violadas: {[vw['window'] for vw in alert.metadata['violated_windows']]}")
            
            # Mostrar formato de mensaje simplificado
            from alertio.types import format_alert_title, get_alert_config
            config = get_alert_config(alert.alert_type)
            title = format_alert_title(alert.alert_type, symbol)
            
            from alertio.telegram import TelegramNotifier
            notifier = TelegramNotifier(bot_token="test", chat_id="test")
            formatted_message = notifier._format_price_alert(alert, title, config)
            
            print(f"      Mensaje formateado:")
            print(f"      {formatted_message.replace(chr(10), chr(10) + '      ')}")
        else:
            print(f"   ⏸️  Sin alertas (no se superaron umbrales)")
    
    print(f"\n📈 RESUMEN:")
    print(f"   Símbolos analizados: {len(test_data)}")
    print(f"   Alertas generadas: {total_alerts}")
    print(f"   Ratio de alertas: {total_alerts/len(test_data):.1%}")
    
    # Verificar que se genera máximo 1 alerta por símbolo
    for symbol, row in test_data.items():
        alerts = scan_for_alerts(symbol, row, return_thresholds=return_thresholds)
        if len(alerts) > 1:
            print(f"❌ ERROR: {symbol} generó {len(alerts)} alertas (debería ser máximo 1)")
            return False
    
    print(f"\n✅ PRUEBA EXITOSA: Se genera máximo 1 alerta por símbolo")
    return True

def test_telegram_formatting():
    """Prueba el formato de mensajes de Telegram"""
    
    print("\n📱 Probando formato de mensajes de Telegram...")
    print("=" * 60)
    
    # Importar TelegramNotifier
    from alertio.telegram import TelegramNotifier
    
    # Crear notificador de prueba (sin enviar)
    notifier = TelegramNotifier(
        bot_token="test_token",
        chat_id="test_chat"
    )
    
    # Crear datos de prueba
    test_data = create_test_data()
    return_thresholds = {
        1: {'min': -0.04, 'max': 0.04},
        5: {'min': -0.07, 'max': 0.07},
        10: {'min': -0.10, 'max': 0.10},
        20: {'min': -0.15, 'max': 0.15}
    }
    
    for symbol, row in test_data.items():
        alerts = scan_for_alerts(symbol, row, return_thresholds=return_thresholds)
        
        if alerts:
            alert = alerts[0]
            
            # Simular formato de mensaje
            from alertio.types import format_alert_title, get_alert_config
            config = get_alert_config(alert.alert_type)
            title = format_alert_title(alert.alert_type, symbol)
            
            formatted_message = notifier._format_price_alert(alert, title, config)
            
            print(f"\n📨 Mensaje formateado para {symbol}:")
            print("-" * 40)
            print(formatted_message)
            print("-" * 40)

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de alertas consolidadas...")
    
    # Ejecutar pruebas
    success = test_consolidated_alerts()
    
    if success:
        test_telegram_formatting()
        print("\n🎉 Todas las pruebas completadas exitosamente!")
    else:
        print("\n❌ Algunas pruebas fallaron")
        sys.exit(1)
