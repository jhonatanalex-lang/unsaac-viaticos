import os
import re
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import database as db
import sunat
import extractor
import report_generator

# Cargar variables de entorno
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados para Perfil Institucional
PERFIL_NOMBRE, PERFIL_DNI, PERFIL_CELULAR, PERFIL_TIPO, PERFIL_DEP, PERFIL_CORREO = range(6)

# Estados para Nueva Comisión
RES_NUM, RES_FECHA, RES_DESTINO, RES_FECHAS_VIAJE, RES_MONTO = range(6, 11)

# Estado para Consulta RUC
ESPERANDO_RUC_CONSULTA = 20

# Directorio de fotos y documentos
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "comprobantes_fotos")
os.makedirs(UPLOADS_DIR, exist_ok=True)

def obtener_teclado_principal() -> ReplyKeyboardMarkup:
    """Devuelve el teclado con todas las opciones institucionales."""
    teclado = [
        [KeyboardButton("📊 Ver Saldo / 100%"), KeyboardButton("🧾 Mis Gastos")],
        [KeyboardButton("🔍 Consultar RUC"), KeyboardButton("👤 Mi Perfil")],
        [KeyboardButton("➕ Nueva Comisión"), KeyboardButton("🏁 Cerrar y Descargar")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

def generar_barra_progreso(gastado: float, total: float, longitud: int = 12) -> str:
    if total <= 0:
        return "[────────────] 0%"
    porcentaje = min(gastado / total, 1.0)
    relleno = int(porcentaje * longitud)
    barra = "█" * relleno + "░" * (longitud - relleno)
    pct_texto = f"{int((gastado / total) * 100)}%"
    return f"[{barra}] {pct_texto}"

def verificar_coherencia_lugar(lugar_gasto: str, destino_comision: str) -> str:
    if not lugar_gasto or not destino_comision:
        return ""
    lugar_low = lugar_gasto.lower()
    destino_low = destino_comision.lower()
    palabras_dest = [p for p in re.findall(r"\w+", destino_low) if len(p) > 3]
    coincide = any(p in lugar_low for p in palabras_dest)
    ciudades_principales = ["lima", "arequipa", "puno", "tacna", "ica", "trujillo", "chiclayo", "huancayo"]
    otra_ciudad = [c for c in ciudades_principales if c in lugar_low and c not in destino_low]
    if not coincide and otra_ciudad:
        return (
            f"⚠️ *ALERTA DE RUTA / LUGAR:* Tu comisión es a *{destino_comision}*, pero este comprobante "
            f"figura emitido en *{lugar_gasto}*. "
            f"Contabilidad podría observar si el gasto se hizo fuera del itinerario autorizado."
        )
    return ""

# --- Comandos Principales ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.registrar_o_actualizar_usuario(user.id, user.full_name)
    perfil = db.obtener_usuario(user.id)
    
    comision_activa = db.obtener_comision_activa(user.id)
    
    perfil_incompleto = not (perfil and perfil.get("dni") and perfil.get("celular"))
    aviso_perfil = ""
    if perfil_incompleto:
        aviso_perfil = (
            "\n\n💡 *Configuración Inicial:* Completa tus datos con el botón *👤 Mi Perfil* "
            "para que el bot autorellene tus documentos oficiales de la UNSAAC."
        )

    if comision_activa:
        msg = (
            f"👋 ¡Hola, *{user.first_name}*!\n\n"
            f"Tienes una comisión *ACTIVA*:\n"
            f"📌 *Resolución:* `{comision_activa['numero_resolucion']}`\n"
            f"📍 *Destino:* {comision_activa['destino']}\n"
            f"💰 *Monto Asignado:* S/ {comision_activa['monto_asignado']:.2f}\n\n"
            f"📸 Envíame fotos o PDFs de tus boletas para escanearlas y llevar la cuenta."
            f"{aviso_perfil}"
        )
    else:
        msg = (
            f"👋 ¡Hola, *{user.first_name}*!\n"
            f"Bienvenido a tu *Asistente de Rendición de Cuentas para Comisiones (UNSAAC)*.\n\n"
            f"Presiona *➕ Nueva Comisión* para iniciar un viaje o *👤 Mi Perfil* para verificar tus datos."
            f"{aviso_perfil}"
        )
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

# --- Flujo: Perfil Institucional ---

async def cmd_ver_o_editar_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    perfil = db.obtener_usuario(user_id)
    
    if perfil and perfil.get("dni") and perfil.get("celular"):
        teclado = [[InlineKeyboardButton("✏️ Modificar mis datos", callback_data="editar_perfil")]]
        msg = (
            f"👤 *TU PERFIL INSTITUCIONAL (UNSAAC)*\n\n"
            f"• *Nombre:* {perfil.get('nombre')}\n"
            f"• *DNI:* {perfil.get('dni')}\n"
            f"• *Celular:* {perfil.get('celular')}\n"
            f"• *Personal:* {perfil.get('tipo_personal')}\n"
            f"• *Dependencia/Facultad:* {perfil.get('dependencia_facultad')}\n"
            f"• *Correo:* {perfil.get('correo_institucional')}\n\n"
            f"💡 *¿Deseas corregir algún dato?*\n"
            f"Presiona el botón abajo o escribe /editar_perfil en cualquier momento."
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(teclado))
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "📝 *Configuración de Perfil Institucional (UNSAAC)*\n\n"
            "Solo te pediré estos datos una sola vez para autorellenar tus formatos oficiales.\n\n"
            "1️⃣ Por favor, ingresa tu **Nombre Completo** (Nombres y Apellidos):",
            parse_mode="Markdown"
        )
        return PERFIL_NOMBRE

async def cmd_iniciar_edicion_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia directamente la edición del perfil."""
    await update.message.reply_text(
        "📝 *Modificar Perfil Institucional (UNSAAC)*\n\n"
        "1️⃣ Ingresa tu **Nombre Completo** (Nombres y Apellidos):",
        parse_mode="Markdown"
    )
    return PERFIL_NOMBRE

async def callback_editar_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *Modificar Perfil Institucional*\n\n"
        "1️⃣ Ingresa tu **Nombre Completo** (Nombres y Apellidos):",
        parse_mode="Markdown"
    )
    return PERFIL_NOMBRE

async def perfil_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["p_nombre"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Ingresa tu número de **DNI** (8 dígitos):", parse_mode="Markdown")
    return PERFIL_DNI

async def perfil_recibir_dni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dni = update.message.text.strip()
    if not (len(dni) == 8 and dni.isdigit()):
        await update.message.reply_text("❌ El DNI debe tener 8 dígitos. Intenta nuevamente:")
        return PERFIL_DNI
    context.user_data["p_dni"] = dni
    await update.message.reply_text("3️⃣ Ingresa tu número de **Celular / Teléfono**:", parse_mode="Markdown")
    return PERFIL_CELULAR

async def perfil_recibir_celular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["p_celular"] = update.message.text.strip()
    
    teclado = [
        [InlineKeyboardButton("👨‍🏫 Docente", callback_data="tipo_Docente"), InlineKeyboardButton("🏢 Administrativo", callback_data="tipo_Administrativo")],
        [InlineKeyboardButton("🎓 Alumno", callback_data="tipo_Alumno"), InlineKeyboardButton("📌 Otros", callback_data="tipo_Otros")]
    ]
    await update.message.reply_text(
        "4️⃣ Selecciona tu **Tipo de Personal** en la UNSAAC:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(teclado)
    )
    return PERFIL_TIPO

async def perfil_recibir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = query.data.replace("tipo_", "")
    context.user_data["p_tipo"] = tipo
    
    etiqueta = "Facultad" if tipo in ["Docente", "Alumno"] else "Dependencia / Oficina"
    await query.edit_message_text(f"5️⃣ Ingresa tu **{etiqueta}** institucional (ej. Facultad de Ingeniería Eléctrica o Unidad de Abastecimiento):")
    return PERFIL_DEP

async def perfil_recibir_dep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["p_dep"] = update.message.text.strip()
    await update.message.reply_text("6️⃣ Finalmente, ingresa tu **Correo Electrónico Institucional** (ej. usuario@unsaac.edu.pe):")
    return PERFIL_CORREO

async def perfil_recibir_correo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correo = update.message.text.strip()
    user_id = update.effective_user.id
    
    db.actualizar_perfil_completo(
        telegram_id=user_id,
        nombre=context.user_data["p_nombre"],
        dni=context.user_data["p_dni"],
        celular=context.user_data["p_celular"],
        tipo_personal=context.user_data["p_tipo"],
        dependencia_facultad=context.user_data["p_dep"],
        correo_institucional=correo
    )
    
    await update.message.reply_text(
        "✅ *¡Perfil Institucional Guardado con Éxito!*\n\n"
        "A partir de ahora, cada formato que generes se completará automáticamente con estos datos.",
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )
    return ConversationHandler.END

# --- Flujo: Nueva Comisión + Entrega Inmediata Formato 1 ---

async def cmd_nueva_comision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    perfil = db.obtener_usuario(user_id)
    
    # Si el perfil no está completo, pedirlo primero
    if not (perfil and perfil.get("dni") and perfil.get("celular")):
        await update.message.reply_text(
            "⚠️ Antes de crear tu primera comisión, necesitamos registrar tu perfil institucional una sola vez.\n"
            "Presiona el botón *👤 Mi Perfil* para configurarlo.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return ConversationHandler.END
        
    comision_activa = db.obtener_comision_activa(user_id)
    if comision_activa:
        await update.message.reply_text(
            f"⚠️ Ya tienes una comisión activa (`{comision_activa['numero_resolucion']}`).\n"
            f"Primero debes finalizarla con el botón *🏁 Cerrar y Descargar*.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
        
    await update.message.reply_text(
        "📝 *Nueva Comisión de Servicios (UNSAAC)*\n\n"
        "1️⃣ Ingresa el **Número de Resolución** rectoral o administrativa\n"
        "(Ejemplo: `R-0450-2026-UNSAAC` o `045-2026`):",
        parse_mode="Markdown"
    )
    return RES_NUM

async def comision_recibir_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["res_num"] = update.message.text.strip()
    await update.message.reply_text(
        "2️⃣ Ingresa la **Fecha de la Resolución**\n"
        "(Ejemplo: `15 de marzo de 2026` o escribe `hoy`):",
        parse_mode="Markdown"
    )
    return RES_FECHA

async def comision_recibir_fecha_res(update: Update, context: ContextTypes.DEFAULT_TYPE):
    f_res = update.message.text.strip()
    if f_res.lower() == "hoy":
        hoy = datetime.now()
        f_res = f"{hoy.day} de {report_generator.MESES_ES[hoy.month]} de {hoy.year}"
    context.user_data["res_fecha"] = f_res
    await update.message.reply_text(
        "3️⃣ ¿Cuál es el **Lugar de Destino** de la comisión?\n"
        "(Ejemplo: `Sicuani - Canchis`, `Quillabamba`, etc.):",
        parse_mode="Markdown"
    )
    return RES_DESTINO

async def comision_recibir_destino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["res_destino"] = update.message.text.strip()
    await update.message.reply_text(
        "4️⃣ Ingresa las **Fechas del Viaje** que figura en la resolución\n"
        "(Ejemplo: `Del 18 al 21 de marzo de 2026`):",
        parse_mode="Markdown"
    )
    return RES_FECHAS_VIAJE

async def comision_recibir_fechas_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["res_fechas_viaje"] = update.message.text.strip()
    await update.message.reply_text(
        "5️⃣ ¿Cuál es el **Monto Total Asignado** en soles según la resolución?\n"
        "(Ejemplo: `800` o `1200.00`):",
        parse_mode="Markdown"
    )
    return RES_MONTO

async def comision_recibir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace("S/", "").replace(",", "").strip()
    try:
        monto = float(texto)
        if monto <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Por favor ingresa un número válido (ej. `800.00`). Intenta nuevamente:")
        return RES_MONTO
        
    user_id = update.effective_user.id
    res_num = context.user_data["res_num"]
    res_fecha = context.user_data["res_fecha"]
    destino = context.user_data["res_destino"]
    fechas_viaje = context.user_data["res_fechas_viaje"]
    
    comision_id = db.crear_comision(
        telegram_id=user_id,
        numero_resolucion=res_num,
        fecha_resolucion=res_fecha,
        destino=destino,
        fechas_viaje_texto=fechas_viaje,
        monto_asignado=monto,
        fecha_inicio=datetime.now().strftime("%d/%m/%Y")
    )
    
    await update.message.reply_text("⏳ *Generando tu Formulario 1 (Declaración de Compromiso)...*", parse_mode="Markdown")
    
    # Generar y enviar Formulario 1 automáticamente
    try:
        ruta_f1 = report_generator.generar_formulario_1(comision_id)
        with open(ruta_f1, "rb") as f1_file:
            await update.message.reply_document(
                document=f1_file,
                filename=f"FORMULARIO_1_COMPROMISO_{res_num.replace('/', '_')}.docx",
                caption=(
                    f"✅ *¡Comisión Aperturada Exitosamente!*\n\n"
                    f"📄 *Resolución:* `{res_num}`\n"
                    f"📍 *Destino:* {destino}\n"
                    f"💵 *Monto:* S/ {monto:.2f}\n\n"
                    f"📥 **Aquí tienes tu FORMATO Nº 1:**\n"
                    f"Descárgalo, imprímelo y fírmalo para que Tesorería te habilite los viáticos.\n\n"
                    f"Buen viaje. En ruta solo envíame las fotos o PDFs de tus boletas."
                ),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error generando Formato 1: {e}")
        await update.message.reply_text("✅ Comisión creada, pero hubo un detalle al exportar Formato 1. Se podrá descargar luego.")

    return ConversationHandler.END

async def cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.", reply_markup=obtener_teclado_principal())
    return ConversationHandler.END

# --- Flujo: Ver Saldo y Cobertura 100% ---

async def cmd_ver_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    comision = db.obtener_comision_activa(user_id)
    
    if not comision:
        await update.message.reply_text(
            "ℹ️ No tienes ninguna comisión activa en este momento.\nUsa *➕ Nueva Comisión* para iniciar una.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return
        
    resumen = db.obtener_resumen_gastos(comision["id"])
    asignado = comision["monto_asignado"]
    gastado = resumen["total_gastado"]
    saldo_restante = asignado - gastado
    barra = generar_barra_progreso(gastado, asignado)
    
    if saldo_restante > 0:
        alerta_cobertura = (
            f"⏳ *Te faltan:* `S/ {saldo_restante:.2f}` para cubrir el *100%* del viático.\n"
            f"💡 *Nota:* El dinero no justificado con comprobantes deberá ser devuelto a la cuenta de la UNSAAC."
        )
    elif saldo_restante == 0:
        alerta_cobertura = "🎯 *¡Cubriste exactamente el 100% de la resolución!*"
    else:
        alerta_cobertura = (
            f"⚠️ *Has sobrepasado el monto en:* `S/ {abs(saldo_restante):.2f}`\n"
            f"(Verifica si la institución reembolsa excedentes o si será gasto asumido)."
        )
        
    desglose = ""
    if resumen["por_concepto"]:
        desglose = "\n\n📂 *Desglose por rubro:*\n"
        for item in resumen["por_concepto"]:
            desglose += f"• {item['concepto']}: S/ {item['total']:.2f} ({item['cantidad']} docs)\n"
            
    mensaje = (
        f"📊 *ESTADO DE RENDICIÓN DE CUENTAS*\n"
        f"📌 *Resolución:* `{comision['numero_resolucion']}` ({comision['destino']})\n\n"
        f"💵 *Monto Asignado:* S/ {asignado:.2f}\n"
        f"🧾 *Total Rendido:* S/ {gastado:.2f} ({resumen['total_items']} comprobantes)\n"
        f"📈 *Avance:* {barra}\n\n"
        f"{alerta_cobertura}"
        f"{desglose}"
    )
    
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

# --- Flujo: Lista de Comprobantes ---

async def cmd_mis_gastos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    comision = db.obtener_comision_activa(user_id)
    
    if not comision:
        await update.message.reply_text("No tienes comisiones activas.", reply_markup=obtener_teclado_principal())
        return
        
    comprobantes = db.listar_comprobantes(comision["id"])
    if not comprobantes:
        await update.message.reply_text("Aún no has registrado ningún comprobante en esta comisión.", reply_markup=obtener_teclado_principal())
        return
        
    msg = f"🧾 *Comprobantes Registrados ({len(comprobantes)}):*\n\n"
    for idx, c in enumerate(comprobantes, 1):
        estado_icon = "✅" if not c["alerta_sunat"] or "sin observaciones" in c["alerta_sunat"].lower() else "⚠️"
        lugar_str = f"📍 {c['lugar']} | " if c.get('lugar') else ""
        msg += (
            f"{idx}. {estado_icon} *{c['tipo_comprobante']}* - S/ {c['monto']:.2f}\n"
            f"   🏢 {c['razon_social'] or 'RUC: ' + (c['ruc'] or 'S/N')}\n"
            f"   🏷️ {c['concepto']} | {lugar_str}📅 {c['fecha_emision'] or 'Hoy'}\n"
        )
        if c["alerta_sunat"] and "sin observaciones" not in c["alerta_sunat"].lower():
            msg += f"   _{c['alerta_sunat']}_\n"
        msg += "\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=obtener_teclado_principal(user.id))

# --- Flujo: Consulta RUC Directa ---

async def cmd_iniciar_consulta_ruc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 *Consulta Rápida de RUC SUNAT*\n\n"
        "Ingresa los **11 dígitos** del RUC que deseas verificar antes de realizar tu consumo o compra:",
        parse_mode="Markdown"
    )
    return ESPERANDO_RUC_CONSULTA

async def responder_consulta_ruc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    match = re.search(r"\b(10|20)\d{9}\b", texto)
    
    if not match:
        await update.message.reply_text(
            "❌ RUC no válido. Debe tener 11 dígitos numéricos y comenzar con 10 o 20.\n"
            "Intenta de nuevo o escribe /cancelar:"
        )
        return ESPERANDO_RUC_CONSULTA
        
    ruc = match.group(0)
    msg_espera = await update.message.reply_text(f"🔍 Consultando RUC `{ruc}` en SUNAT...", parse_mode="Markdown")
    
    info = sunat.consultar_ruc_sunat(ruc)
    await msg_espera.delete()
    
    estado = info.get("estado", "DESCONOCIDO")
    condicion = info.get("condicion", "DESCONOCIDO")
    estado_icon = "✅" if "ACTIVO" in estado else "❌"
    condicion_icon = "✅" if "HABIDO" in condicion else "❌"
    
    advertencia = ""
    if "ACTIVO" not in estado:
        advertencia += "\n🚨 *ALERTA:* Este RUC NO está ACTIVO. Contabilidad rechazará comprobantes de este negocio."
    if "HABIDO" not in condicion:
        advertencia += "\n🚨 *ALERTA:* Este RUC figura como NO HABIDO."
    if not advertencia:
        advertencia = "\n✨ *ESTADO ÓPTIMO:* El proveedor está habilitado para emitir comprobantes válidos."

    msg = (
        f"📋 *FICHA RUC SUNAT:*\n\n"
        f"🏢 *Razón Social:* `{info.get('razon_social')}`\n"
        f"🆔 *RUC:* `{ruc}`\n"
        f"📍 *Dirección:* {info.get('direccion') or 'No especificada'}\n"
        f"📊 *Estado:* {estado_icon} *{estado}*\n"
        f"🏠 *Condición:* {condicion_icon} *{condicion}*\n"
        f"🏷️ *Actividad:* {info.get('actividad_economica') or 'General'}\n"
        f"{advertencia}"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=obtener_teclado_principal(user.id))
    return ConversationHandler.END

# --- Flujo: Recepción de Fotos y Documentos (PDF) ---

async def procesar_archivo_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    comision = db.obtener_comision_activa(user_id)
    
    if not comision:
        await update.message.reply_text(
            "⚠️ Primero debes iniciar una comisión para registrar comprobantes.\n"
            "Presiona *➕ Nueva Comisión*.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return
        
    es_pdf = False
    if update.message.photo:
        archivo = update.message.photo[-1]
        extension = "jpg"
    elif update.message.document:
        doc = update.message.document
        if not (doc.mime_type == "application/pdf" or (doc.file_name and doc.file_name.lower().endswith(".pdf"))):
            await update.message.reply_text("❌ Por favor envía una foto o un archivo en formato **PDF**.")
            return
        archivo = doc
        extension = "pdf"
        es_pdf = True
    else:
        return

    msg_status = await update.message.reply_text("🔍 *Analizando comprobante con IA y SUNAT...*", parse_mode="Markdown")
    
    file_info = await context.bot.get_file(archivo.file_id)
    nombre_archivo = f"user_{user_id}_com_{comision['id']}_{int(datetime.now().timestamp())}.{extension}"
    ruta_guardada = os.path.join(UPLOADS_DIR, nombre_archivo)
    await file_info.download_to_drive(ruta_guardada)
    context.user_data["ultima_foto"] = ruta_guardada

    # 1. Validación rápida de resolución y tamaño mínimo de imagen
    calidad = extractor.validar_calidad_imagen(ruta_guardada)
    if not calidad.get("valido", True):
        await msg_status.delete()
        await update.message.reply_text(
            f"⚠️ *FOTO CON RESOLUCIÓN MUY BAJA*\n\n"
            f"{calidad['motivo']}\n\n"
            f"📸 *Sugerencia:* Por favor vuelve a tomar la foto más de cerca, enfocando bien los números y con buena luz.\n\n"
            f"💡 *O escribe el gasto manualmente en el chat, ej:* `85.00 20123456789 Calca`",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    # 2. Análisis con IA con tiempo límite estricto (Timeout de 10s)
    try:
        datos_extraidos = await asyncio.wait_for(
            asyncio.to_thread(extractor.analizar_comprobante, ruta_guardada),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        await msg_status.delete()
        await update.message.reply_text(
            f"⏳ *TIEMPO MÁXIMO DE VERIFICACIÓN SUPERADO*\n\n"
            f"El escaneo tomó más de 10 segundos debido a baja nitidez, poca luz o lentitud de red.\n\n"
            f"📸 *Por favor toma una foto más clara y con buena iluminación.*\n\n"
            f"💡 *O ingresa el monto y RUC por texto en 5 segundos, ej:* `75.00 20456789012`",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    # 3. Detección de comprobante no legible según la IA
    if datos_extraidos.get("legible") is False:
        motivo = datos_extraidos.get("motivo", "La foto está muy borrosa, movida o con poca luz.")
        await msg_status.delete()
        await update.message.reply_text(
            f"🔍 *COMPROBANTE NO LEGIBLE*\n\n"
            f"La IA detectó que el comprobante no se puede leer con certeza:\n_{motivo}_\n\n"
            f"🛡️ *Para evitar errores en tu rendición contable:*\n"
            f"📸 Vuelve a tomar la foto enfocando bien los datos.\n\n"
            f"💡 *O ingresa el gasto manualmente en el chat, ej:* `85.00 20123456789 Sicuani`",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return
    
    monto = datos_extraidos.get("monto", 0.0)
    ruc = datos_extraidos.get("ruc", "")
    tipo_doc = datos_extraidos.get("tipo_comprobante", "Boleta")
    serie_num = datos_extraidos.get("serie_numero", "")
    fecha = datos_extraidos.get("fecha", datetime.now().strftime("%Y-%m-%d"))
    lugar = datos_extraidos.get("lugar", "")
    nombre_comercial = datos_extraidos.get("nombre_comercial", "")
    descripcion = datos_extraidos.get("descripcion", "")
    concepto_sug = datos_extraidos.get("concepto_sugerido", "Alimentación")
    
    context.user_data["gasto_monto"] = monto
    context.user_data["gasto_ruc"] = ruc
    context.user_data["gasto_tipo"] = tipo_doc
    context.user_data["gasto_serie"] = serie_num
    context.user_data["gasto_fecha"] = fecha
    context.user_data["gasto_lugar"] = lugar
    context.user_data["gasto_nombre_comercial"] = nombre_comercial
    context.user_data["gasto_descripcion"] = descripcion
    context.user_data["origen_extraccion"] = datos_extraidos.get("origen", "MANUAL")
    
    # 🛡️ Control Antiduplicados: Verificar si este comprobante ya se subió previamente
    duplicado = db.verificar_comprobante_duplicado(
        comision_id=comision["id"],
        ruc=ruc,
        serie_numero=serie_num,
        monto=monto,
        fecha_emision=fecha
    )
    if duplicado:
        await msg_status.delete()
        await update.message.reply_text(
            f"🚨 *¡ALERTA DE COMPROBANTE DUPLICADO!* 🚨\n\n"
            f"Este comprobante **ya fue registrado previamente** en esta comisión:\n\n"
            f"• 📄 *Documento:* {duplicado['tipo_comprobante']} `{duplicado['serie_numero'] or 'S/N'}`\n"
            f"• 🏢 *Proveedor:* {duplicado['razon_social']} (RUC: `{duplicado['ruc']}`)\n"
            f"• 💵 *Monto:* S/ {duplicado['monto']:.2f}\n"
            f"• 🏷️ *Rubro anterior:* {duplicado['concepto']}\n"
            f"• 📅 *Registrado el:* {duplicado['fecha_registro']}\n\n"
            f"🛡️ *Para no inflar tu presupuesto ni cometer faltas en la rendición, este comprobante NO ha sido duplicado.*",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return
    
    if monto > 0 or ruc:
        info_sunat = {}
        alerta_sunat = ""
        razon_social = datos_extraidos.get("razon_social", "")
        
        if ruc:
            await msg_status.edit_text("🔍 *Consultando RUC en SUNAT...*", parse_mode="Markdown")
            info_sunat = sunat.consultar_ruc_sunat(ruc)
            if info_sunat.get("valido"):
                razon_social = info_sunat.get("razon_social", razon_social)
                evaluacion = sunat.generar_alerta_completa_sunat(info_sunat, concepto_sug, descripcion)
                alerta_sunat = evaluacion["resumen_alerta"]
                if not lugar and info_sunat.get("direccion"):
                    lugar = info_sunat.get("direccion")
                    context.user_data["gasto_lugar"] = lugar
                
        context.user_data["gasto_razon"] = razon_social
        context.user_data["info_sunat"] = info_sunat
        context.user_data["alerta_sunat"] = alerta_sunat
        
        alerta_ruta = verificar_coherencia_lugar(lugar, comision["destino"])
        
        teclado = [
            [
                InlineKeyboardButton("🍲 Alimentación", callback_data="guardar_Alimentación"),
                InlineKeyboardButton("🏨 Hospedaje", callback_data="guardar_Hospedaje")
            ],
            [
                InlineKeyboardButton("🚗 Movilidad", callback_data="guardar_Movilidad"),
                InlineKeyboardButton("📄 Otros / DJ", callback_data="guardar_Otros")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(teclado)
        
        texto_sunat = f"\n\n🔍 *Validación SUNAT:*\n• Proveedor: `{razon_social}`\n• Estado/Condición: {info_sunat.get('estado', 'N/D')} / {info_sunat.get('condicion', 'N/D')}" if ruc else ""
        if alerta_sunat:
            texto_sunat += f"\n• {alerta_sunat}"
        if alerta_ruta:
            texto_sunat += f"\n\n{alerta_ruta}"
            
        texto_comercio = f"🏷️ *Comercio:* `{nombre_comercial}`\n" if nombre_comercial else ""
        await msg_status.delete()
        await update.message.reply_text(
            f"⚡ *¡Datos Detectados Automáticamente!*\n\n"
            f"📄 *Tipo:* {tipo_doc} `{serie_num}`\n"
            f"💵 *Monto Total:* **S/ {monto:.2f}**\n"
            f"{texto_comercio}"
            f"🏢 *RUC:* `{ruc or 'No detectado'}`\n"
            f"📍 *Lugar detectado:* `{lugar or 'Por confirmar'}`"
            f"{texto_sunat}\n\n"
            f"👇 *Selecciona el concepto para guardarlo:*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await msg_status.delete()
        await update.message.reply_text(
            "📸 ¡Archivo recibido con éxito!\n\n"
            "ℹ️ No se detectó un código legible automáticamente.\n\n"
            "Por favor indícame el monto, RUC y Lugar así:\n"
            "`Monto RUC Lugar`  (Ejemplo: `45.00 20601234567 Sicuani`)",
            parse_mode="Markdown"
        )

async def procesar_datos_manuales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    comision = db.obtener_comision_activa(user_id)
    if not comision:
        return
        
    texto = update.message.text.strip()
    partes = texto.split()
    if not partes:
        return
        
    try:
        monto_str = partes[0].replace("S/", "").replace(",", "").strip()
        monto = float(monto_str)
    except ValueError:
        return
        
    ruc = ""
    lugar = ""
    if len(partes) > 1:
        if len(partes[1]) == 11 and partes[1].isdigit():
            ruc = partes[1]
            if len(partes) > 2:
                lugar = " ".join(partes[2:])
        else:
            lugar = " ".join(partes[1:])
            
    context.user_data["gasto_monto"] = monto
    context.user_data["gasto_ruc"] = ruc
    context.user_data["gasto_tipo"] = "Factura" if ruc.startswith("20") else ("Boleta" if ruc else "Recibo/Ticket")
    context.user_data["gasto_serie"] = ""
    context.user_data["gasto_lugar"] = lugar
    context.user_data["gasto_fecha"] = datetime.now().strftime("%Y-%m-%d")
    context.user_data["gasto_descripcion"] = ""
    
    teclado = [
        [
            InlineKeyboardButton("🍲 Alimentación", callback_data="guardar_Alimentación"),
            InlineKeyboardButton("🏨 Hospedaje", callback_data="guardar_Hospedaje")
        ],
        [
            InlineKeyboardButton("🚗 Movilidad", callback_data="guardar_Movilidad"),
            InlineKeyboardButton("📄 Otros / DJ", callback_data="guardar_Otros")
        ]
    ]
    await update.message.reply_text(
        f"💵 *Monto:* S/ {monto:.2f}\n"
        f"🏢 *RUC:* `{ruc or 'Sin RUC'}`\n"
        f"📍 *Lugar:* `{lugar or 'Destino comisión'}`\n\n"
        f"¿A qué concepto pertenece este gasto?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(teclado)
    )

async def callback_guardar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    concepto = query.data.replace("guardar_", "")
    user_id = query.from_user.id
    comision = db.obtener_comision_activa(user_id)
    if not comision:
        await query.edit_message_text("⚠️ No se encontró la comisión activa.")
        return
        
    monto = context.user_data.get("gasto_monto", 0.0)
    ruc = context.user_data.get("gasto_ruc", "")
    tipo_doc = context.user_data.get("gasto_tipo", "Boleta")
    serie_num = context.user_data.get("gasto_serie", "")
    fecha_emision = context.user_data.get("gasto_fecha", datetime.now().strftime("%Y-%m-%d"))
    foto_path = context.user_data.get("ultima_foto", "")
    razon_social = context.user_data.get("gasto_razon", "Proveedor Local")
    lugar = context.user_data.get("gasto_lugar", "")
    descripcion = context.user_data.get("gasto_descripcion", "")
    
    estado_sunat = ""
    condicion_sunat = ""
    actividad_economica = ""
    alerta_texto = ""
    
    if ruc:
        info_sunat = context.user_data.get("info_sunat")
        if not info_sunat:
            info_sunat = sunat.consultar_ruc_sunat(ruc)
        if info_sunat.get("valido"):
            razon_social = info_sunat.get("razon_social", razon_social)
            estado_sunat = info_sunat.get("estado", "")
            condicion_sunat = info_sunat.get("condicion", "")
            actividad_economica = info_sunat.get("actividad_economica", "")
            evaluacion = sunat.generar_alerta_completa_sunat(info_sunat, concepto, descripcion)
            alerta_texto = evaluacion["resumen_alerta"]
            if not lugar and info_sunat.get("direccion"):
                lugar = info_sunat.get("direccion")
    
    if not lugar:
        lugar = comision["destino"]
        
    # Doble chequeo antiduplicados antes de guardar en la base de datos
    duplicado = db.verificar_comprobante_duplicado(
        comision_id=comision["id"],
        ruc=ruc,
        serie_numero=serie_num,
        monto=monto,
        fecha_emision=fecha_emision
    )
    if duplicado:
        await query.edit_message_text(
            f"🚨 *¡COMPROBANTE DUPLICADO!* 🚨\n\n"
            f"Este comprobante ya se encuentra registrado en tu comisión activa:\n"
            f"• Documento: {duplicado['tipo_comprobante']} `{duplicado['serie_numero'] or 'S/N'}`\n"
            f"• Importe: S/ {duplicado['monto']:.2f}\n"
            f"• Fecha: {duplicado['fecha_emision']}\n\n"
            f"🛡️ *No ha sido duplicado.*",
            parse_mode="Markdown"
        )
        return
        
    nombre_comercial = context.user_data.get("gasto_nombre_comercial", "")
    db.registrar_comprobante(
        comision_id=comision["id"],
        tipo_comprobante=tipo_doc,
        serie_numero=serie_num,
        ruc=ruc,
        razon_social=razon_social,
        nombre_comercial=nombre_comercial,
        monto=monto,
        fecha_emision=fecha_emision,
        concepto=concepto,
        lugar=lugar,
        estado_sunat=estado_sunat,
        condicion_sunat=condicion_sunat,
        actividad_economica=actividad_economica,
        alerta_sunat=alerta_texto,
        foto_path=foto_path
    )
    
    resumen = db.obtener_resumen_gastos(comision["id"])
    asignado = comision["monto_asignado"]
    gastado = resumen["total_gastado"]
    saldo = asignado - gastado
    barra = generar_barra_progreso(gastado, asignado)
    
    alerta_bloque = f"\n🔍 *SUNAT:* {alerta_texto}\n" if alerta_texto else ""
    alerta_ruta = verificar_coherencia_lugar(lugar, comision["destino"])
    if alerta_ruta:
        alerta_bloque += f"\n{alerta_ruta}\n"
    
    mensaje_final = (
        f"✅ *¡Comprobante Guardado Exitosamente!*\n\n"
        f"🧾 *{tipo_doc}:* S/ {monto:.2f}\n"
        f"🏢 *Emisor:* {razon_social} `({ruc or 'S/N'})`\n"
        f"📍 *Lugar:* {lugar}\n"
        f"🏷️ *Rubro:* {concepto}\n"
        f"{alerta_bloque}\n"
        f"📊 *Progreso hacia el 100%:*\n"
        f"Gastado: S/ {gastado:.2f} de S/ {asignado:.2f}\n"
        f"{barra}\n"
        f"Te faltan: *S/ {max(saldo, 0.0):.2f}*"
    )
    
    await query.edit_message_text(mensaje_final, parse_mode="Markdown")

# --- Flujo: Cierre de Comisión y Descarga de Formatos 2, 3 y PDF ---

async def cmd_cerrar_y_descargar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    comision = db.obtener_comision_activa(user_id)
    
    if not comision:
        await update.message.reply_text(
            "ℹ️ No tienes ninguna comisión activa que cerrar.\nUsa *➕ Nueva Comisión* para iniciar una.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return
        
    cid = comision["id"]
    res_num = comision["numero_resolucion"]
    asignado = comision["monto_asignado"]
    resumen = db.obtener_resumen_gastos(cid)
    gastado = resumen["total_gastado"]
    saldo_devolver = max(asignado - gastado, 0.0)
    
    msg_espera = await update.message.reply_text("⏳ *Generando expediente oficial de rendición (Formatos 2, 3 y PDF de boletas)...*", parse_mode="Markdown")
    
    # 1. Generar FORMATO 2 (Word)
    ruta_f2 = report_generator.generar_formato_2(cid)
    # 2. Generar FORMATO 3 (Excel)
    ruta_f3 = report_generator.generar_formato_3(cid)
    # 3. Generar PDF Consolidado de Comprobantes
    ruta_pdf_comprobantes = report_generator.generar_pdf_consolidado_comprobantes(cid)
    
    # Cerrar la comisión en base de datos
    db.cerrar_comision(cid)
    await msg_espera.delete()
    
    # Mensaje resumen
    texto_devolucion = ""
    if saldo_devolver > 0:
        texto_devolucion = (
            f"\n💰 *SALDO PENDIENTE POR DEVOLVER:* `S/ {saldo_devolver:.2f}`\n"
            f"⚠️ Deberás realizar el depósito de este importe a la cuenta corriente institucional de la UNSAAC y adjuntar el voucher."
        )
    else:
        texto_devolucion = "\n🎯 *¡Cubriste el 100% de la resolución con comprobantes válidos!*"

    await update.message.reply_text(
        f"🏁 *¡COMISIÓN DE SERVICIO CERRADA!*\n\n"
        f"📌 *Resolución:* `{res_num}`\n"
        f"💵 *Monto Asignado:* S/ {asignado:.2f}\n"
        f"🧾 *Total Rendido:* S/ {gastado:.2f} ({resumen['total_items']} comprobantes)\n"
        f"{texto_devolucion}\n\n"
        f"📦 *A continuación te envío tus 3 documentos listos para imprimir y firmar:*",
        parse_mode="Markdown"
    )
    
    # Enviar Formato 2 (.docx)
    with open(ruta_f2, "rb") as f2:
        await update.message.reply_document(
            document=f2,
            filename=f"FORMATO_2_SOLICITUD_{res_num.replace('/', '_')}.docx",
            caption="1️⃣ **FORMATO Nº 2:** Solicitud de Rendición dirigida al Director General de Administración (Word)."
        )
        
    # Enviar Formato 3 (.xlsx)
    with open(ruta_f3, "rb") as f3:
        await update.message.reply_document(
            document=f3,
            filename=f"FORMATO_3_RESUMEN_GASTOS_{res_num.replace('/', '_')}.xlsx",
            caption="2️⃣ **FORMATO Nº 3:** Resumen y Planilla de Gastos (Excel con fórmulas y comprobantes)."
        )
        
    # Enviar PDF Consolidado
    if ruta_pdf_comprobantes:
        with open(ruta_pdf_comprobantes, "rb") as f_pdf:
            await update.message.reply_document(
                document=f_pdf,
                filename=f"ANEXO_COMPROBANTES_{res_num.replace('/', '_')}.pdf",
                caption="3️⃣ **ANEXO COMPLETO:** Todas tus fotos y PDFs de boletas compiladas en un solo archivo A4 listo para imprimir."
            )
            
    await update.message.reply_text(
        "✨ ¡Listo! Tu rendición ha sido procesada con éxito.\nYa puedes iniciar una nueva comisión cuando lo requieras.",
        reply_markup=obtener_teclado_principal()
    )

def main():
    if not BOT_TOKEN or BOT_TOKEN == "tu_token_aqui_de_botfather":
        print("ERROR: Configura TELEGRAM_BOT_TOKEN en .env")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    db.init_db()

    # Handler: Perfil Institucional
    conv_perfil = ConversationHandler(
        entry_points=[
            CommandHandler("perfil", cmd_ver_o_editar_perfil),
            CommandHandler("editar_perfil", cmd_iniciar_edicion_perfil),
            MessageHandler(filters.Regex("^👤 Mi Perfil$"), cmd_ver_o_editar_perfil),
            CallbackQueryHandler(callback_editar_perfil, pattern="^editar_perfil$")
        ],
        states={
            PERFIL_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, perfil_recibir_nombre)],
            PERFIL_DNI: [MessageHandler(filters.TEXT & ~filters.COMMAND, perfil_recibir_dni)],
            PERFIL_CELULAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, perfil_recibir_celular)],
            PERFIL_TIPO: [CallbackQueryHandler(perfil_recibir_tipo, pattern="^tipo_")],
            PERFIL_DEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, perfil_recibir_dep)],
            PERFIL_CORREO: [MessageHandler(filters.TEXT & ~filters.COMMAND, perfil_recibir_correo)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_conversacion)],
    )

    # Handler: Nueva Comisión
    conv_comision = ConversationHandler(
        entry_points=[
            CommandHandler("nueva_comision", cmd_nueva_comision),
            MessageHandler(filters.Regex("^➕ Nueva Comisión$"), cmd_nueva_comision)
        ],
        states={
            RES_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, comision_recibir_num)],
            RES_FECHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, comision_recibir_fecha_res)],
            RES_DESTINO: [MessageHandler(filters.TEXT & ~filters.COMMAND, comision_recibir_destino)],
            RES_FECHAS_VIAJE: [MessageHandler(filters.TEXT & ~filters.COMMAND, comision_recibir_fechas_viaje)],
            RES_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, comision_recibir_monto)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_conversacion)],
    )

    # Handler: Consulta RUC
    conv_consulta_ruc = ConversationHandler(
        entry_points=[
            CommandHandler("consulta_ruc", cmd_iniciar_consulta_ruc),
            MessageHandler(filters.Regex("^🔍 Consultar RUC$"), cmd_iniciar_consulta_ruc)
        ],
        states={
            ESPERANDO_RUC_CONSULTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, responder_consulta_ruc)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar_conversacion)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", cmd_ver_saldo))
    app.add_handler(CommandHandler("gastos", cmd_mis_gastos))
    app.add_handler(CommandHandler("cerrar", cmd_cerrar_y_descargar))
    
    app.add_handler(MessageHandler(filters.Regex("^📊 Ver Saldo / 100%$"), cmd_ver_saldo))
    app.add_handler(MessageHandler(filters.Regex("^🧾 Mis Gastos$"), cmd_mis_gastos))
    app.add_handler(MessageHandler(filters.Regex("^🏁 Cerrar y Descargar$"), cmd_cerrar_y_descargar))
    
    app.add_handler(conv_perfil)
    app.add_handler(conv_comision)
    app.add_handler(conv_consulta_ruc)
    
    # Manejador de FOTOS y DOCUMENTOS (PDF)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.PDF, procesar_archivo_comprobante))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_datos_manuales))
    app.add_handler(CallbackQueryHandler(callback_guardar_gasto, pattern="^guardar_"))

    print("🤖 Bot UNSAAC 100% activo con gestión de Formatos 1, 2, 3 y PDF compilado...")
    app.run_polling()

if __name__ == "__main__":
    main()
