import os
import re
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

try:
    import cv2
    from pyzbar.pyzbar import decode
except Exception:
    cv2 = None
    decode = None

import pymupdf # PyMuPDF
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def decodificar_qr_sunat(texto_qr: str) -> Optional[Dict[str, Any]]:
    """
    Parsea la cadena del código QR estándar de SUNAT:
    RUC | TIPO_DOC | SERIE | NUMERO | IGV | TOTAL | FECHA | TIPO_DOC_CLIENTE | NUM_DOC_CLIENTE
    """
    partes = [p.strip() for p in texto_qr.split("|")]
    if len(partes) >= 6:
        ruc = partes[0]
        tipo_code = partes[1]
        serie = partes[2]
        numero = partes[3]
        
        # Mapeo de tipos de comprobante de SUNAT
        tipos_map = {
            "01": "Factura",
            "03": "Boleta",
            "07": "Nota de Crédito",
            "08": "Nota de Débito",
            "R1": "Recibo por Honorarios"
        }
        tipo_comprobante = tipos_map.get(tipo_code, "Comprobante")
        
        try:
            total = float(partes[5].replace(",", ""))
        except (ValueError, IndexError):
            total = 0.0
            
        fecha = partes[6] if len(partes) > 6 else ""
        
        return {
            "origen": "QR_SUNAT",
            "ruc": ruc if len(ruc) == 11 and ruc.isdigit() else "",
            "tipo_comprobante": tipo_comprobante,
            "serie_numero": f"{serie}-{numero}",
            "monto": total,
            "fecha": fecha
        }
    return None

def escanear_qr_imagen(ruta_imagen: str) -> Optional[Dict[str, Any]]:
    """Busca códigos QR en la imagen."""
    if not decode or not cv2:
        return None
    try:
        img = cv2.imread(ruta_imagen)
        if img is None:
            return None
        codigos = decode(img)
        for c in codigos:
            data = c.data.decode("utf-8", errors="ignore")
            if "|" in data:
                resultado = decodificar_qr_sunat(data)
                if resultado and resultado["ruc"]:
                    return resultado
    except Exception as e:
        print(f"Error escaneando QR: {e}")
    return None

def extraer_datos_pdf(ruta_pdf: str) -> Dict[str, Any]:
    """Extrae texto y busca QRs en un documento PDF."""
    resultado = {
        "origen": "PDF_TEXTO",
        "ruc": "",
        "tipo_comprobante": "Boleta",
        "serie_numero": "",
        "monto": 0.0,
        "fecha": "",
        "razon_social": ""
    }
    
    try:
        doc = pymupdf.open(ruta_pdf)
        texto_completo = ""
        
        # 1. Buscar primero QR en las imágenes del PDF
        for page_num in range(len(doc)):
            page = doc[page_num]
            texto_completo += page.get_text() + "\n"
            
            for img_info in page.get_images():
                xref = img_info[0]
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                
                # Decodificar imagen temporal si hay soporte QR
                if decode and cv2:
                    import numpy as np
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if img_cv is not None:
                        qrs = decode(img_cv)
                        for q in qrs:
                            data = q.data.decode("utf-8", errors="ignore")
                            if "|" in data:
                                qr_res = decodificar_qr_sunat(data)
                                if qr_res and qr_res["ruc"]:
                                    doc.close()
                                    return qr_res
                                
        doc.close()
        
        # 2. Si no hay QR, buscar por expresiones regulares en el texto
        # RUC
        match_ruc = re.search(r"\b(10|20)\d{9}\b", texto_completo)
        if match_ruc:
            resultado["ruc"] = match_ruc.group(0)
            
        # Tipo
        if "FACTURA" in texto_completo.upper():
            resultado["tipo_comprobante"] = "Factura"
        elif "BOLETA" in texto_completo.upper():
            resultado["tipo_comprobante"] = "Boleta"
        elif "RECIBO" in texto_completo.upper():
            resultado["tipo_comprobante"] = "Recibo"
            
        # Total
        match_total = re.search(r"(?:TOTAL|IMPORTE\s*TOTAL|IMPORTE)\s*[:S/\.\$]*\s*([0-9]+[,\.][0-9]{2})", texto_completo, re.IGNORECASE)
        if match_total:
            monto_str = match_total.group(1).replace(",", ".")
            try:
                resultado["monto"] = float(monto_str)
            except ValueError:
                pass
                
        # Fecha
        match_fecha = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", texto_completo)
        if match_fecha:
            resultado["fecha"] = match_fecha.group(1)
            
        return resultado
    except Exception as e:
        print(f"Error procesando PDF: {e}")
        return resultado

def extraer_con_gemini_vision(ruta_archivo: str) -> Optional[Dict[str, Any]]:
    """Usa Gemini Flash para leer comprobantes impresos o manuscritos."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
        
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        # Subir o pasar bytes del archivo
        with open(ruta_archivo, "rb") as f:
            archivo_bytes = f.read()
            
        mime_type = "application/pdf" if ruta_archivo.lower().endswith(".pdf") else "image/jpeg"
        
        prompt = """
        Eres un experto auditor contable de comprobantes de pago de Perú (SUNAT).
        Analiza esta imagen/documento de una boleta, factura o ticket de gastos de viaje/viáticos.
        Extrae la siguiente información en formato JSON estricto:
        {
          "tipo_comprobante": "Factura" | "Boleta" | "Ticket" | "Declaración Jurada" | "Pasaje",
          "serie_numero": "ej. B001-000451 o 001-0000418",
          "ruc": "RUC del EMISOR (11 dígitos que empieza con 10 o 20)",
          "razon_social": "Nombre de la persona natural o empresa titular del RUC",
          "nombre_comercial": "Nombre comercial, de fantasía o del establecimiento que figura en el encabezado principal (ej. Productos 'Lorito', Restaurant El Valle, Hotel Imperial)",
          "lugar": "Distrito, ciudad o dirección que figure en el comprobante (ej. Sicuani, Calca, Cusco, Lima)",
          "fecha": "YYYY-MM-DD o DD/MM/YYYY",
          "monto_total": 0.00,
          "descripcion": "breve resumen de los productos o servicios consumidos",
          "concepto_sugerido": "Alimentación" | "Hospedaje" | "Movilidad" | "Otros"
        }
        Responde ÚNICAMENTE con el bloque JSON, sin texto adicional ni markdown.
        """
        
        # Intentar modelos modernos de Gemini
        modelos_a_probar = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
        response = None
        for mod in modelos_a_probar:
            try:
                response = client.models.generate_content(
                    model=mod,
                    contents=[
                        types.Part.from_bytes(data=archivo_bytes, mime_type=mime_type),
                        prompt
                    ]
                )
                if response and response.text:
                    break
            except Exception as emod:
                continue
                
        if not response or not response.text:
            return None
        
        texto_resp = response.text.strip()
        # Limpiar posibles bloques ```json ... ```
        if "```" in texto_resp:
            texto_resp = re.sub(r"^```json\s*", "", texto_resp, flags=re.MULTILINE)
            texto_resp = re.sub(r"^```\s*", "", texto_resp, flags=re.MULTILINE)
            texto_resp = texto_resp.strip()
            
        data = json.loads(texto_resp)
        monto_raw = str(data.get("monto_total", data.get("total", 0.0))).replace(",", "").replace("S/", "").strip()
        try:
            monto_final = float(monto_raw)
        except ValueError:
            monto_final = 0.0
            
        return {
            "origen": "GEMINI_IA",
            "ruc": str(data.get("ruc", "")).strip(),
            "razon_social": data.get("razon_social", ""),
            "nombre_comercial": str(data.get("nombre_comercial", "")).strip(),
            "tipo_comprobante": data.get("tipo_comprobante", "Boleta"),
            "serie_numero": data.get("serie_numero", ""),
            "monto": monto_final,
            "fecha": data.get("fecha", ""),
            "lugar": str(data.get("lugar", "")).strip(),
            "descripcion": data.get("descripcion", ""),
            "concepto_sugerido": data.get("concepto_sugerido", "Alimentación")
        }
    except Exception as e:
        print(f"Error en Gemini Vision: {e}")
        return None

def analizar_comprobante(ruta_archivo: str) -> Dict[str, Any]:
    """
    Función orquestadora de extracción:
    1. Si es PDF, lee texto y QR en PDF.
    2. Si es imagen, busca código QR SUNAT.
    3. Si tiene Gemini API Key configurado, usa IA para leer cualquier texto manuscrito o impreso.
    4. Retorna el resultado consolidado.
    """
    es_pdf = ruta_archivo.lower().endswith(".pdf")
    
    # 1. Intentar con Gemini si la API key está disponible (máxima precisión para manuscrito)
    if os.getenv("GEMINI_API_KEY"):
        res_ai = extraer_con_gemini_vision(ruta_archivo)
        if res_ai and (res_ai.get("monto", 0) > 0 or res_ai.get("ruc")):
            return res_ai
            
    # 2. Si es PDF, intentar extracción de texto nativo y QR
    if es_pdf:
        res_pdf = extraer_datos_pdf(ruta_archivo)
        if res_pdf.get("ruc") or res_pdf.get("monto", 0) > 0:
            return res_pdf
            
    # 3. Si es imagen, buscar QR de SUNAT
    res_qr = escanear_qr_imagen(ruta_archivo)
    if res_qr:
        return res_qr
        
    # 4. No se pudo extraer automáticamente
    return {
        "origen": "MANUAL",
        "ruc": "",
        "razon_social": "",
        "tipo_comprobante": "Boleta",
        "serie_numero": "",
        "monto": 0.0,
        "fecha": "",
        "concepto_sugerido": ""
    }
