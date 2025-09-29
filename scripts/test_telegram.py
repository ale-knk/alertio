#!/usr/bin/env python3
"""
Script para probar la integración con Telegram.

Uso:
    python scripts/test_telegram.py BOT_TOKEN CHAT_ID
"""

import sys
import os
import logging
from pathlib import Path

# Agregar src al path para importar alertio
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    # Buscar .env en el directorio del proyecto
    project_root = Path(__file__).parent.parent
    env_file = project_root / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Cargadas variables de entorno desde {env_file}")
    else:
        load_dotenv()  # Intentar cargar desde directorio actual
except ImportError:
    print("⚠️  python-dotenv no instalado, usando solo variables de sistema")

from alertio.telegram import TelegramNotifier


def setup_logging():
    """Configura logging para ver detalles"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def test_telegram_integration(bot_token: str, chat_id: str):
    """Prueba completa de la integración con Telegram"""
    
    print("🤖 Probando integración con Telegram...\n")
    
    try:
        # Crear notificador
        notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
        print("✅ Notificador creado correctamente")
        
        # Obtener información del bot
        print("\n📋 Información del bot:")
        bot_info = notifier.get_bot_info()
        if bot_info:
            print(f"   Nombre: {bot_info.get('first_name', 'N/A')}")
            print(f"   Username: @{bot_info.get('username', 'N/A')}")
            print(f"   ID: {bot_info.get('id', 'N/A')}")
        else:
            print("   ❌ No se pudo obtener información del bot")
        
        # Probar conexión
        print("\n🔗 Probando conexión...")
        if notifier.test_connection():
            print("✅ Mensaje de prueba enviado correctamente")
        else:
            print("❌ Error enviando mensaje de prueba")
            return False
        
        # Probar alerta formateada
        print("\n📈 Probando alerta formateada...")
        success = notifier.send_alert(
            symbol="AAPL",
            message="Retorno 1d ≤ -3.0% (actual -4.2%)",
            price=150.25
        )
        
        if success:
            print("✅ Alerta de prueba enviada correctamente")
        else:
            print("❌ Error enviando alerta de prueba")
            return False
        
        print("\n🎉 ¡Todas las pruebas pasaron! Tu bot está listo.")
        return True
        
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False


def main():
    setup_logging()
    
    # Obtener credenciales de argumentos o variables de entorno
    bot_token = None
    chat_id = None
    
    if len(sys.argv) == 3:
        bot_token = sys.argv[1]
        chat_id = sys.argv[2]
    elif len(sys.argv) == 1:
        # Sin argumentos, usar variables de entorno
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
    else:
        print("❌ Uso: python scripts/test_telegram.py [BOT_TOKEN CHAT_ID]")
        print("\n💡 Opciones:")
        print("   1. Con argumentos: python scripts/test_telegram.py BOT_TOKEN CHAT_ID")
        print("   2. Con .env: crea archivo .env y ejecuta sin argumentos")
        print("   3. Con variables de entorno del sistema")
        sys.exit(1)
    
    if not bot_token or not chat_id:
        print("❌ Bot token y chat ID son requeridos")
        print("\n💡 Configura las variables:")
        print("   - En .env: TELEGRAM_BOT_TOKEN=... y TELEGRAM_CHAT_ID=...")
        print("   - O pásalas como argumentos")
        sys.exit(1)
    
    print(f"🔑 Usando bot token: ...{bot_token[-10:]}")
    print(f"💬 Usando chat ID: {chat_id}")
    
    success = test_telegram_integration(bot_token, chat_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
