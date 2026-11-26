import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def consultar_ruc_con_ia(ruc: str):
    prompt = f"""
    Eres un auditor contable de SUNAT en Perú.
    Busca y consulta la información oficial del RUC {ruc} de Perú (utilizando datos del padrón SUNAT, datosperu, deperu, universodatos, etc.).
    Devuelve ÚNICAMENTE un objeto JSON válido con este formato exacto:
    {{
      "ruc": "{ruc}",
      "razon_social": "Nombre completo o Razón Social registrada",
      "estado": "ACTIVO" o "BAJA DEFINITIVA" o "SUSPENSION TEMPORAL",
      "condicion": "HABIDO" o "NO HABIDO" o "NO HALLADO",
      "actividad_economica": "Descripción de la actividad económica principal o CIIU",
      "direccion": "Dirección fiscal o distrito/departamento"
    }}
    """
    try:
        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        texto = resp.text.strip()
        if "```" in texto:
            texto = re.sub(r"^```json\s*", "", texto, flags=re.MULTILINE)
            texto = re.sub(r"^```\s*", "", texto, flags=re.MULTILINE)
            texto = texto.strip()
        return json.loads(texto)
    except Exception as e:
        print("Error en consulta IA:", e)
        return None

if __name__ == "__main__":
    for test_ruc in ["10072486892", "20100047218"]:
        print(f"\n--- Probando RUC {test_ruc} ---")
        info = consultar_ruc_con_ia(test_ruc)
        print(json.dumps(info, indent=2, ensure_ascii=False))
