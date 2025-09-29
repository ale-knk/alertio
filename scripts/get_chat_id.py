#!/usr/bin/env python3
"""
Script para obtener tu chat_id de Telegram.

Uso:
1. Crea tu bot con @BotFather
2. Envía un mensaje a tu bot
3. Ejecuta: python scripts/get_chat_id.py YOUR_BOT_TOKEN
"""

import sys
import os
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    env_file = project_root / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Cargadas variables desde {env_file}")
    else:
        load_dotenv()
except ImportError:
    pass


def get_chat_id(bot_token: str):
    """Obtiene el chat_id del último mensaje enviado al bot"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("ok"):
            print(f"❌ Error de API: {data.get('description', 'Unknown error')}")
            return
        
        updates = data.get("result", [])
        if not updates:
            print("📭 No hay mensajes. Envía un mensaje a tu bot primero.")
            print("   1. Busca tu bot en Telegram")
            print("   2. Envía cualquier mensaje (ej: /start)")
            print("   3. Ejecuta este script nuevamente")
            return
        
        # Obtener el último mensaje
        last_update = updates[-1]
        message = last_update.get("message", {})
        chat = message.get("chat", {})
        
        chat_id = chat.get("id")
        chat_type = chat.get("type")
        first_name = chat.get("first_name", "")
        username = chat.get("username", "")
        
        print("✅ ¡Chat ID encontrado!")
        print(f"   Chat ID: {chat_id}")
        print(f"   Tipo: {chat_type}")
        print(f"   Nombre: {first_name}")
        if username:
            print(f"   Username: @{username}")
        
        print("\n🔧 Variables de entorno:")
        print(f"   export TELEGRAM_BOT_TOKEN='{bot_token}'")
        print(f"   export TELEGRAM_CHAT_ID='{chat_id}'")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")


if __name__ == "__main__":
    # Obtener token de argumentos o variables de entorno
    bot_token = None
    
    if len(sys.argv) == 2:
        bot_token = sys.argv[1]
    elif len(sys.argv) == 1:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    else:
        print("❌ Uso: python scripts/get_chat_id.py [BOT_TOKEN]")
        print("\n💡 También puedes usar .env con TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    
    if not bot_token or len(bot_token) < 10:
        print("❌ Token inválido o no encontrado")
        print("💡 Configura TELEGRAM_BOT_TOKEN en .env o pásalo como argumento")
        sys.exit(1)
    
    print(f"🔑 Usando bot token: ...{bot_token[-10:]}")
    get_chat_id(bot_token)
