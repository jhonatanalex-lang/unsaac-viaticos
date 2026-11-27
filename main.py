import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot de Rendicion de Viaticos UNSAAC activo 24/7")
        
    def log_message(self, format, *args):
        return # Silenciar logs HTTP para mantener limpia la consola

def run_health_server():
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 [Cloud Keep-Alive] Servidor activo en puerto {port}...")
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def keep_alive_self_ping():
    """
    Realiza un ping cada 9 minutos al dominio público de Render
    para evitar que el servidor gratuito entre en hibernación por inactividad.
    """
    import requests
    time.sleep(45) # Esperar 45 segundos para que el servidor esté 100% arriba
    cloud_url = os.getenv("RENDER_EXTERNAL_URL", "https://unsaac-viaticos.onrender.com")
    print(f"🔄 [Keep-Alive Ping] Monitoreando {cloud_url} cada 9 minutos...")
    
    while True:
        try:
            r = requests.get(cloud_url, timeout=20)
            print(f"💓 [Keep-Alive Ping] Status {r.status_code} - Servidor mantenido despierto.")
        except Exception as e:
            print(f"⚠️ [Keep-Alive Ping]: {e}")
        time.sleep(9 * 60) # 9 minutos (Render duerme a los 15 min)

if __name__ == "__main__":
    print("==================================================")
    print("  UNSAAC - Bot de Rendición de Viáticos (24/7)    ")
    print("==================================================")
    
    # 1. Iniciar servidor ligero keep-alive para Render en hilo secundario
    web_thread = threading.Thread(target=run_health_server, daemon=True)
    web_thread.start()
    time.sleep(1)
    
    # 2. Iniciar bucle de auto-ping para evitar la hibernación de los 15 minutos
    ping_thread = threading.Thread(target=keep_alive_self_ping, daemon=True)
    ping_thread.start()
    
    # 3. Iniciar el bot de Telegram en el hilo principal
    from bot import main as bot_main
    bot_main()
