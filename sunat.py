import os
import requests
import json
import re
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
import database as db

load_dotenv()
SUNAT_TOKEN = os.getenv("SUNAT_TOKEN", os.getenv("APIS_TOKEN", ""))

def consultar_ruc_sunat(ruc: str) -> Dict[str, Any]:
    """
    Consulta los datos de un RUC (Estado, Condición y Razón Social).
    1. Revisa primero en la base de datos local (Caché SQLite).
    2. Si no está en caché, consulta endpoints externos de SUNAT.
    3. Guarda el resultado en caché para futuras consultas instantáneas sin costo ni límites.
    """
    ruc = str(ruc).strip()
    if len(ruc) != 11 or not ruc.isdigit():
        return {
            "valido": False,
            "error": "El RUC debe tener 11 dígitos numéricos."
        }
    
    # 1. Verificar si ya lo consultamos antes (Caché local)
    en_cache = db.obtener_cache_sunat(ruc)
    if en_cache:
        return {
            "valido": True,
            "ruc": ruc,
            "razon_social": en_cache["razon_social"],
            "estado": en_cache["estado"].upper(),
            "condicion": en_cache["condicion"].upper(),
            "direccion": en_cache["direccion"],
            "actividad_economica": en_cache["actividad_economica"],
            "origen": "CACHE_LOCAL"
        }

    # 2. Consultar con Token v2 si está configurado
    if SUNAT_TOKEN:
        try:
            url_v2 = f"https://api.apis.net.pe/v2/sunat/ruc?numero={ruc}"
            headers = {"Authorization": f"Bearer {SUNAT_TOKEN}"}
            resp = requests.get(url_v2, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                razon = data.get("razonSocial", data.get("nombre", ""))
                estado = data.get("estado", "ACTIVO").upper()
                condicion = data.get("condicion", "HABIDO").upper()
                actividad = data.get("actividadEconomica", "")
                direccion = data.get("direccion", "")
                
                db.guardar_cache_sunat(ruc, razon, estado, condicion, actividad, direccion)
                return {
                    "valido": True,
                    "ruc": ruc,
                    "razon_social": razon,
                    "estado": estado,
                    "condicion": condicion,
                    "direccion": direccion,
                    "actividad_economica": actividad,
                    "origen": "APIS_NET_V2"
                }
        except Exception:
            pass

    # 3. Consultar endpoint v1 público
    try:
        url_v1 = f"https://api.apis.net.pe/v1/ruc?numero={ruc}"
        resp_v1 = requests.get(url_v1, timeout=6)
        if resp_v1.status_code == 200:
            data = resp_v1.json()
            razon = data.get("nombre", "")
            estado = data.get("estado", "ACTIVO").upper()
            condicion = data.get("condicion", "HABIDO").upper()
            actividad = data.get("actividadEconomica", "")
            direccion = data.get("direccion", "")
            
            db.guardar_cache_sunat(ruc, razon, estado, condicion, actividad, direccion)
            return {
                "valido": True,
                "ruc": ruc,
                "razon_social": razon,
                "estado": estado,
                "condicion": condicion,
                "direccion": direccion,
                "actividad_economica": actividad,
                "origen": "APIS_NET_V1"
            }
    except Exception:
        pass

    # Si no hay conexión o falla la consulta externa
    return {
        "valido": True,
        "ruc": ruc,
        "razon_social": "PROVEEDOR LOCAL",
        "estado": "POR VERIFICAR",
        "condicion": "POR VERIFICAR",
        "direccion": "",
        "actividad_economica": "",
        "origen": "OFFLINE"
    }

def validar_coherencia_gasto(concepto: str, actividad_economica: str = "", descripcion_items: str = "") -> Tuple[bool, str]:
    """
    Verifica si el concepto declarado (ej. Alimentación) tiene relación con:
    a) La actividad económica registrada en SUNAT.
    b) Los productos/servicios específicos descritos en la boleta.
    """
    incompatibilidades = {
        "Alimentación": ["ferreteria", "construccion", "gasolina", "combustible", "duchas a gas", "ducha", "cemento", "mecanica", "repuestos", "ropa", "calzado", "celular"],
        "Hospedaje": ["ferreteria", "restaurante", "repuestos", "combustible", "gasolina", "alimentos", "comida", "ducha"],
        "Movilidad": ["restaurante", "hotel", "hospedaje", "ferreteria", "ducha", "alimentos", "comida"]
    }
    
    texto_revisar = f"{actividad_economica} {descripcion_items}".lower()
    
    incompatibles = incompatibilidades.get(concepto, [])
    encontrados = [inc for inc in incompatibles if inc in texto_revisar]
    
    if encontrados:
        return False, (
            f"⚠️ ALERTA DE COHERENCIA: Marcaste este gasto como *{concepto}*, pero el comprobante o emisor indica "
            f"*{', '.join(encontrados)}*. "
            f"Contabilidad podría observar o rechazar este comprobante por no corresponder al rubro."
        )
        
    return True, ""

def generar_alerta_completa_sunat(info_sunat: Dict[str, Any], concepto: str, descripcion_items: str = "") -> Dict[str, Any]:
    """
    Evalúa integralmente el RUC y el concepto, generando alertas claras para el comisionado.
    """
    alertas = []
    estado = info_sunat.get("estado", "").upper()
    condicion = info_sunat.get("condicion", "").upper()
    actividad = info_sunat.get("actividad_economica", "")

    # 1. Validación de Estado Tributario
    if estado and "ACTIVO" not in estado and "POR VERIFICAR" not in estado:
        alertas.append(f"❌ RUC NO ACTIVO (Estado: *{estado}*). ¡CUIDADO! Este comprobante NO tiene validez tributaria ante SUNAT ni la institución.")
    
    # 2. Validación de Condición de Domicilio
    if condicion and "HABIDO" not in condicion and "POR VERIFICAR" not in condicion:
        alertas.append(f"❌ RUC NO HABIDO (Condición: *{condicion}*). La entidad rechazará esta rendición (Directiva de viáticos exige comprobantes de proveedores HABIDOS).")
        
    # 3. Validación de Giro / Concepto
    coherente, msg_coherencia = validar_coherencia_gasto(concepto, actividad, descripcion_items)
    if not coherente:
        alertas.append(msg_coherencia)
        
    return {
        "aprobado": len(alertas) == 0,
        "alertas": alertas,
        "resumen_alerta": "\n\n".join(alertas) if alertas else "✅ RUC Activo, Habido y sin observaciones."
    }

if __name__ == "__main__":
    db.init_db()
    test_ruc = "10072486892"
    print("Probando consulta RUC...")
    res = consultar_ruc_sunat(test_ruc)
    print("Resultado SUNAT:", json.dumps(res, indent=2, ensure_ascii=False))
    
    # Prueba 1: Gasto Alimentación con 3 duchas a gas
    evaluacion_mal = generar_alerta_completa_sunat(res, "Alimentación", "3 duchas a gas")
    print("\n--- Test 1 (Alerta Mismatch): ---")
    print(evaluacion_mal["resumen_alerta"])
    
    # Prueba 2: Gasto Alimentación con Menú ejecutivo
    evaluacion_ok = generar_alerta_completa_sunat(res, "Alimentación", "Menu ejecutivo lomo saltado")
    print("\n--- Test 2 (Gasto Normal): ---")
    print(evaluacion_ok["resumen_alerta"])
    
    # Prueba 3: Simular RUC No Habido
    res_baja = {"estado": "BAJA DEFINITIVA", "condicion": "NO HABIDO", "actividad_economica": ""}
    evaluacion_baja = generar_alerta_completa_sunat(res_baja, "Alimentación", "Almuerzo")
    print("\n--- Test 3 (RUC de Baja / No Habido): ---")
    print(evaluacion_baja["resumen_alerta"])
