import os
import sys
import threading
import time
import uvicorn
from dotenv import load_dotenv

load_dotenv()

def run_web():
    """Inicia el servidor web FastAPI para la Mini App y el health-check de Render."""
    from webapp_server import app
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 [Web Server] Iniciando FastAPI en el puerto {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

def run_bot():
    """Inicia el bot de Telegram."""
    from bot import main as bot_main
    print("🤖 [Telegram Bot] Iniciando daemon de Telegram...")
    bot_main()

if __name__ == "__main__":
    print("==================================================")
    print("  UNSAAC - Sistema de Rendición de Viáticos       ")
    print("  Iniciando servicios unificados (Bot + MiniApp)  ")
    print("==================================================")
    
    # 1. Iniciar servidor Web en un hilo secundario
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Dar 1 segundo para que levante el servidor web
    time.sleep(1)
    
    # 2. Iniciar el bot de Telegram en el hilo principal
    run_bot()
