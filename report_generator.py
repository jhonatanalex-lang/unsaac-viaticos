import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
import docx
import openpyxl
import pymupdf # PyMuPDF

import database as db
from numero_a_letras import numero_a_letras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "generados")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

TEMPLATE_F1 = os.path.join(BASE_DIR, "FORMULARIO 1 personal -autorizacion-descuento.docx")
TEMPLATE_F2 = os.path.join(BASE_DIR, "FORMATO Nº 2 - RENDICION DE CUENTAS COMISION DE SERVICIO.docx")
TEMPLATE_F3 = os.path.join(BASE_DIR, "FORMATO Nº 3 - RENDICION DE CUENTAS-COMISION DE SERVICIO.xlsx")

MESES_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

def fecha_a_texto_cusco(fecha_dt: Optional[datetime] = None) -> str:
    if not fecha_dt:
        fecha_dt = datetime.now()
    return f"{fecha_dt.day} de {MESES_ES[fecha_dt.month]} de {fecha_dt.year}"

# --- GENERADOR: FORMULARIO 1 (Al crear comisión) ---

def generar_formulario_1(comision_id: int) -> str:
    comision = db.obtener_comision_por_id(comision_id)
    if not comision:
        raise ValueError(f"No existe la comisión ID {comision_id}")
        
    usuario = db.obtener_usuario(comision["telegram_id"])
    if not usuario:
        usuario = {"nombre": "Comisionado", "dni": "", "celular": "", "tipo_personal": "Administrativo", "dependencia_facultad": ""}

    doc = docx.Document(TEMPLATE_F1)
    
    nombre = usuario.get("nombre", "").upper()
    dni = usuario.get("dni", "")
    celular = usuario.get("celular", "")
    tipo_p = usuario.get("tipo_personal", "Administrativo")
    dep = usuario.get("dependencia_facultad", "")
    
    res_num = comision.get("numero_resolucion", "")
    res_fecha = comision.get("fecha_resolucion", "")
    monto = float(comision.get("monto_asignado", 0.0))
    monto_letras = numero_a_letras(monto)
    
    nota_pago = comision.get("nota_pago", "S/N")
    siaf = comision.get("exp_siaf", "S/N")
    fte_fto = comision.get("fte_fto", "RDR")
    
    hoy = datetime.now()
    fecha_hoy_str = f"Cusco, {hoy.day} de {MESES_ES[hoy.month]} de {hoy.year}."

    for p in doc.paragraphs:
        texto = p.text
        if "Yo," in texto:
            p.text = f"Yo,  {nombre}"
        elif "Identificado con DNI" in texto:
            p.text = f"Identificado con DNI. Nº:  {dni}"
        elif "Celular Nº" in texto or "Teléfono" in texto:
            p.text = f"Teléfono / Celular Nº:  {celular}"
        elif "Personal:" in texto:
            pass # encabezado
        elif "Docente" in texto and "Facultad" in texto:
            p.text = f"Docente              :          Facultad:  {dep}" if tipo_p == "Docente" else "Docente              :          Facultad:  ---"
        elif "Administrativo" in texto and "Dependencia" in texto:
            p.text = f"Administrativo     :          Dependencia:  {dep}" if tipo_p == "Administrativo" else "Administrativo     :          Dependencia:  ---"
        elif "Alumno" in texto and "Facultad" in texto:
            p.text = f"Alumno.              :          Facultad:  {dep}" if tipo_p == "Alumno" else "Alumno.              :          Facultad:  ---"
        elif "Otros." in texto:
            p.text = f"Otros.                 :          {dep}" if tipo_p not in ["Docente", "Administrativo", "Alumno"] else "Otros.                 :          ---"
        elif "Nº. Resolución R-" in texto:
            p.text = (
                f"Nº. Resolución R- {res_num} de fecha {res_fecha or fecha_a_texto_cusco(hoy)} "
                f"EN CASO DE INCUMPLIMIENTO AUTORIZO SE PROCEDA AL DESCUENTO ESTE IMPORTE DE MIS REMUNERACIONES."
            )
        elif "Otorgado por S/." in texto:
            p.text = f"Otorgado por S/. {monto:.2f} ({monto_letras})"
        elif "Nota de pago Nº." in texto:
            p.text = f"Nota de pago Nº: {nota_pago}          Fte. de Fto: {fte_fto}"
        elif "Registro SIAF Nº" in texto:
            p.text = f"Registro SIAF Nº: {siaf}"
        elif "Cusco," in texto and ("2025" in texto or "20" in texto):
            p.text = f"                                                              	{fecha_hoy_str}"
        elif "Nombre completo:" in texto:
            p.text = f"              Nombre completo:  {nombre}"
        elif "DNI.:" in texto and p.text.strip().startswith("DNI.:"):
            p.text = f"              DNI.:  {dni}"

    output_path = os.path.join(OUTPUTS_DIR, f"FORMULARIO_1_COMISION_{comision_id}.docx")
    doc.save(output_path)
    return output_path

# --- GENERADOR: FORMATO 2 (Al cerrar rendición) ---

def generar_formato_2(comision_id: int) -> str:
    comision = db.obtener_comision_por_id(comision_id)
    if not comision:
        raise ValueError(f"No existe la comisión ID {comision_id}")
        
    usuario = db.obtener_usuario(comision["telegram_id"])
    if not usuario:
        usuario = {"nombre": "Comisionado", "dni": "", "celular": "", "correo_institucional": ""}

    doc = docx.Document(TEMPLATE_F2)
    
    nombre = usuario.get("nombre", "").upper()
    dni = usuario.get("dni", "")
    celular = usuario.get("celular", "")
    correo = usuario.get("correo_institucional", "")
    
    res_num = comision.get("numero_resolucion", "")
    res_fecha = comision.get("fecha_resolucion", "")
    monto = float(comision.get("monto_asignado", 0.0))
    fechas_viaje = comision.get("fechas_viaje_texto", f"Del {comision.get('fecha_inicio', '')} al {comision.get('fecha_fin', '')}")
    
    nota_pago = comision.get("nota_pago", "S/N")
    siaf = comision.get("exp_siaf", "S/N")
    fte_fto = comision.get("fte_fto", "RDR")
    planilla = comision.get("planilla_numero", "S/N")
    
    hoy = datetime.now()
    fecha_hoy_str = f"Cusco, {hoy.day} de {MESES_ES[hoy.month]} del {hoy.year}"

    # Reemplazar en párrafos
    for p in doc.paragraphs:
        texto = p.text
        if "Cusco,……." in texto or "Cusco," in texto:
            p.text = fecha_hoy_str
        elif "REF. Resolución Nº R-" in texto:
            p.text = f"\t\t\t\t\t  REF. Resolución Nº R-{res_num} de {res_fecha or fecha_a_texto_cusco(hoy)}"
        elif "Nombre:" in texto:
            p.text = f"Nombre: {nombre}"
        elif "DNI Nº :" in texto:
            p.text = f"\t\t\tDNI Nº : {dni}"
        elif "CELULAR:" in texto:
            p.text = f"\t\t\tCELULAR: {celular}"
        elif "CORREO ELECTRONICO INSTITUCIONAL:" in texto:
            p.text = f"CORREO ELECTRONICO INSTITUCIONAL: {correo}"

    # Reemplazar en Tabla 0
    if doc.tables:
        tabla = doc.tables[0]
        # Fila 1: Fechas del viaje
        if len(tabla.rows) > 1:
            tabla.rows[1].cells[0].text = fechas_viaje
        # Fila 3: Dejar en VACÍO (lo completa la Unidad de Integración Contable)
        if len(tabla.rows) > 3:
            r3 = tabla.rows[3]
            for c_cell in r3.cells:
                c_cell.text = ""

    output_path = os.path.join(OUTPUTS_DIR, f"FORMATO_2_SOLICITUD_{comision_id}.docx")
    doc.save(output_path)
    return output_path

# --- GENERADOR: FORMATO 3 (Excel Resumen de Gastos) ---

def generar_formato_3(comision_id: int) -> str:
    comision = db.obtener_comision_por_id(comision_id)
    if not comision:
        raise ValueError(f"No existe la comisión ID {comision_id}")
        
    comprobantes = db.listar_comprobantes(comision_id)
    wb = openpyxl.load_workbook(TEMPLATE_F3, data_only=False)
    sheet = wb.active
    
    # Formato de Moneda para Soles (ej. S/ 120.00)
    FORMATO_MONEDA = '"S/ "#,##0.00;("S/ "#,##0.00);"-"'

    # 1. Monto Asignado en A. Ingresos
    monto_asignado = float(comision.get("monto_asignado", 0.0))
    fecha_inicio = comision.get("fecha_inicio") or comision.get("fecha_resolucion") or datetime.now().strftime("%d/%m/%Y")
    sheet["B7"] = fecha_inicio
    sheet["J7"] = monto_asignado
    sheet["J7"].number_format = FORMATO_MONEDA
    
    # Mapeo de tipo a nomenclatura UNSAAC
    map_tipo = {
        "Factura": "FACT.",
        "Boleta": "B/V",
        "Ticket": "T",
        "Declaración Jurada": "DD.JJ",
        "Pasaje": "B/VIAJE"
    }
    
    # 2. Llenar comprobantes a partir de la fila 12
    fila_inicio = 12
    for idx, c in enumerate(comprobantes):
        r = fila_inicio + idx
        if r > 38:
            break # Límite de la plantilla estándar
            
        sheet.cell(r, 1).value = float(idx + 1) # N°
        sheet.cell(r, 2).value = c.get("fecha_emision", "") # Fecha
        tipo_abrev = map_tipo.get(c.get("tipo_comprobante", ""), "B/V")
        sheet.cell(r, 3).value = tipo_abrev # Tipo
        sheet.cell(r, 4).value = c.get("serie_numero", "") # Serie-Número
        
        # Proveedor: Priorizar Nombre Comercial de la boleta/factura
        nom_comercial = c.get("nombre_comercial", "").strip()
        razon_soc = c.get("razon_social", "").strip()
        proveedor_final = nom_comercial if nom_comercial else (razon_soc if razon_soc else "Proveedor Local")
        sheet.cell(r, 5).value = proveedor_final
        
        # Concepto + Lugar
        desc = c.get("concepto", "")
        if c.get("lugar"):
            desc += f" ({c['lugar']})"
        sheet.cell(r, 7).value = desc # Descripción
        
        # Importe con formato de moneda Soles
        cell_monto = sheet.cell(r, 10)
        cell_monto.value = float(c.get("monto", 0.0))
        cell_monto.number_format = FORMATO_MONEDA

    # Fila 39: Total Gastos Realizados
    sheet["J39"].value = "=SUM(J12:J38)"
    sheet["J39"].number_format = FORMATO_MONEDA

    # Fila 40: Saldo Diferencia a devolver (si es negativo, es 0)
    sheet["J40"].value = "=IF(J7-J39>0, J7-J39, 0)"
    sheet["J40"].number_format = FORMATO_MONEDA

    output_path = os.path.join(OUTPUTS_DIR, f"FORMATO_3_RESUMEN_GASTOS_{comision_id}.xlsx")
    wb.save(output_path)
    return output_path

# --- GENERADOR: PDF Consolidado de Comprobantes ---

def generar_pdf_consolidado_comprobantes(comision_id: int) -> Optional[str]:
    """
    Compila todas las fotos y PDFs de comprobantes de la comisión
    en un solo archivo PDF listo para imprimir en A4 con encabezados formales.
    """
    comision = db.obtener_comision_por_id(comision_id)
    comprobantes = db.listar_comprobantes(comision_id)
    
    if not comprobantes:
        return None
        
    doc_consolidado = pymupdf.open()
    res_num = comision.get("numero_resolucion", "S/N") if comision else "S/N"
    
    # Dimensiones estándar A4 en puntos (portrait)
    A4_W, A4_H = 595, 842

    for idx, c in enumerate(comprobantes, 1):
        foto_path = c.get("foto_path", "")
        if not foto_path or not os.path.exists(foto_path):
            continue
            
        es_pdf = foto_path.lower().endswith(".pdf")
        
        if es_pdf:
            # Si el comprobante original es un PDF, insertar sus páginas
            try:
                sub_doc = pymupdf.open(foto_path)
                for page in sub_doc:
                    doc_consolidado.insert_pdf(sub_doc, from_page=page.number, to_page=page.number)
                sub_doc.close()
            except Exception as e:
                print(f"Error insertando PDF {foto_path}: {e}")
        else:
            # Si es imagen (JPG/PNG), crear una página A4 limpia
            page = doc_consolidado.new_page(width=A4_W, height=A4_H)
            
            # Texto de encabezado formal
            header_title = f"UNSAAC - RENDICION DE CUENTAS | RES. R-{res_num}"
            header_info = (
                f"COMPROBANTE N° {idx:02d}: {c.get('tipo_comprobante', 'Comprobante')} {c.get('serie_numero', '')} | "
                f"IMPORTE: S/ {c.get('monto', 0.0):.2f}"
            )
            nom_com = c.get("nombre_comercial", "").strip()
            raz_soc = c.get("razon_social", "").strip()
            if nom_com and raz_soc and nom_com.lower() != raz_soc.lower():
                prov_texto = f"{nom_com} | Razón Social: {raz_soc}"
            else:
                prov_texto = nom_com or raz_soc or "Proveedor Local"
                
            header_det = f"PROVEEDOR: {prov_texto} (RUC: {c.get('ruc', 'S/N')}) | LUGAR: {c.get('lugar', 'Cusco')} | FECHA: {c.get('fecha_emision', '')}"
            
            # Dibujar caja de título
            page.draw_rect(pymupdf.Rect(30, 25, A4_W - 30, 75), color=(0.1, 0.2, 0.4), fill=(0.95, 0.96, 0.98), width=1)
            page.insert_text(pymupdf.Point(40, 42), header_title, fontsize=10, fontname="helv", color=(0.1, 0.2, 0.4))
            page.insert_text(pymupdf.Point(40, 56), header_info, fontsize=9, fontname="helv", color=(0.0, 0.0, 0.0))
            page.insert_text(pymupdf.Point(40, 68), header_det, fontsize=8, fontname="helv", color=(0.3, 0.3, 0.3))
            
            # Insertar la foto centrada en la página debajo del encabezado
            rect_foto = pymupdf.Rect(40, 85, A4_W - 40, A4_H - 40)
            try:
                page.insert_image(rect_foto, filename=foto_path, keep_proportion=True)
            except Exception as e:
                print(f"Error insertando imagen {foto_path}: {e}")

    if len(doc_consolidado) == 0:
        doc_consolidado.close()
        return None
        
    output_path = os.path.join(OUTPUTS_DIR, f"ANEXO_COMPROBANTES_COMISION_{comision_id}.pdf")
    doc_consolidado.save(output_path)
    doc_consolidado.close()
    return output_path

if __name__ == "__main__":
    db.init_db()
    print("Probando report_generator...")
    # Crear comisión simulada para probar la generación
    uid = 999999
    db.actualizar_perfil_completo(uid, "JUAN CARLOS PEREZ QUISPE", "23918786", "984123456", "Administrativo", "UNIDAD DE FINANZAS", "juan.perez@unsaac.edu.pe")
    cid = db.crear_comision(uid, "R-0450-2026-UNSAAC", "Sicuani - Canchis", 800.0, "15 de marzo de 2026", "Del 18 al 21 de marzo de 2026")
    
    f1 = generar_formulario_1(cid)
    print("F1 generado:", f1)
    f2 = generar_formato_2(cid)
    print("F2 generado:", f2)
    f3 = generar_formato_3(cid)
    print("F3 generado:", f3)
    pdf_anexo = generar_pdf_consolidado_comprobantes(cid)
    print("PDF Anexo comprobantes:", pdf_anexo)
