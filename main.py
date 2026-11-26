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

if __name__ == "__main__":
    print("==================================================")
    print("  UNSAAC - Bot de Rendición de Viáticos (24/7)    ")
    print("==================================================")
    
    # 1. Iniciar servidor ligero keep-alive para Render en hilo secundario
    web_thread = threading.Thread(target=run_health_server, daemon=True)
    web_thread.start()
    time.sleep(1)
    
    # 2. Iniciar el bot de Telegram en el hilo principal
    from bot import main as bot_main
    bot_main()
