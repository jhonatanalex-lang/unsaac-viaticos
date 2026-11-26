import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db

app = FastAPI(title="UNSAAC Viáticos - Telegram Mini App API")

# Habilitar CORS para permitir llamadas desde el WebView de Telegram
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

class EditarComprobantePayload(BaseModel):
    concepto: str
    monto: float
    lugar: Optional[str] = ""
    nombre_comercial: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(STATIC_DIR, "miniapp.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Mini App de Rendición de Viáticos UNSAAC</h1>"

@app.get("/api/comision/{telegram_id}")
async def api_obtener_comision(telegram_id: int):
    comision = db.obtener_comision_activa(telegram_id)
    usuario = db.obtener_usuario(telegram_id)
    
    if not comision:
        return JSONResponse({
            "activa": False,
            "usuario": dict(usuario) if usuario else None,
            "mensaje": "No tienes una comisión de servicios activa en este momento."
        })
        
    cid = comision["id"]
    resumen = db.obtener_resumen_gastos(cid)
    comprobantes = db.listar_comprobantes(cid)
    
    monto_asignado = float(comision.get("monto_asignado", 0.0))
    total_gastado = float(resumen.get("total_gastado", 0.0))
    saldo_devolver = max(monto_asignado - total_gastado, 0.0)
    
    porcentaje = round((total_gastado / monto_asignado) * 100, 1) if monto_asignado > 0 else 0.0
    
    # Formatear comprobantes para la UI
    lista_comprobantes = []
    for c in comprobantes:
        c_dict = dict(c)
        tiene_foto = bool(c_dict.get("foto_path") and os.path.exists(c_dict["foto_path"]))
        c_dict["tiene_foto"] = tiene_foto
        c_dict["foto_url"] = f"/api/foto/{c_dict['id']}" if tiene_foto else None
        lista_comprobantes.append(c_dict)

    return JSONResponse({
        "activa": True,
        "usuario": dict(usuario) if usuario else None,
        "comision": dict(comision),
        "resumen": {
            "monto_asignado": monto_asignado,
            "total_gastado": total_gastado,
            "saldo_devolver": saldo_devolver,
            "porcentaje": porcentaje,
            "cantidad_comprobantes": len(lista_comprobantes),
            "por_concepto": resumen.get("por_concepto", {})
        },
        "comprobantes": lista_comprobantes
    })

@app.get("/api/foto/{comprobante_id}")
async def api_obtener_foto(comprobante_id: int):
    comp = db.obtener_comprobante_por_id(comprobante_id)
    if not comp or not comp.get("foto_path"):
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
        
    foto_path = comp["foto_path"]
    if not os.path.exists(foto_path):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado")
        
    media_type = "application/pdf" if foto_path.lower().endswith(".pdf") else "image/jpeg"
    return FileResponse(foto_path, media_type=media_type)

@app.delete("/api/comprobante/{comprobante_id}")
async def api_eliminar_comprobante(comprobante_id: int):
    exito = db.eliminar_comprobante(comprobante_id)
    if not exito:
        raise HTTPException(status_code=404, detail="No se pudo eliminar el comprobante")
    return {"success": True, "mensaje": "Comprobante eliminado exitosamente"}

@app.post("/api/comprobante/{comprobante_id}/editar")
async def api_editar_comprobante(comprobante_id: int, payload: EditarComprobantePayload):
    exito = db.actualizar_comprobante(
        comprobante_id=comprobante_id,
        concepto=payload.concepto,
        monto=payload.monto,
        lugar=payload.lugar or "",
        nombre_comercial=payload.nombre_comercial or ""
    )
    if not exito:
        raise HTTPException(status_code=404, detail="No se pudo actualizar el comprobante")
    return {"success": True, "mensaje": "Comprobante actualizado exitosamente"}

if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor Mini App en http://0.0.0.0:8000")
    uvicorn.run("webapp_server:app", host="0.0.0.0", port=8000, reload=True)
