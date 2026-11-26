import sqlite3
import os
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "rendiciones.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa y migra las tablas de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla de Usuarios / Perfil Institucional
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                telegram_id INTEGER PRIMARY KEY,
                nombre TEXT,
                dni TEXT,
                celular TEXT DEFAULT '',
                tipo_personal TEXT DEFAULT 'Administrativo', -- Docente, Administrativo, Alumno, Otros
                dependencia_facultad TEXT DEFAULT '',
                correo_institucional TEXT DEFAULT '',
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migraciones automáticas para columnas nuevas en usuarios
        cursor.execute("PRAGMA table_info(usuarios)")
        cols_usr = [c[1] for c in cursor.fetchall()]
        for col, tipo in [
            ("celular", "TEXT DEFAULT ''"),
            ("tipo_personal", "TEXT DEFAULT 'Administrativo'"),
            ("dependencia_facultad", "TEXT DEFAULT ''"),
            ("correo_institucional", "TEXT DEFAULT ''")
        ]:
            if col not in cols_usr:
                cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
        
        # Tabla de Comisiones de Servicios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comisiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                numero_resolucion TEXT NOT NULL,
                fecha_resolucion TEXT DEFAULT '',
                destino TEXT NOT NULL,
                fechas_viaje_texto TEXT DEFAULT '',
                monto_asignado REAL NOT NULL,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                nota_pago TEXT DEFAULT 'S/N',
                exp_siaf TEXT DEFAULT 'S/N',
                fte_fto TEXT DEFAULT 'RDR',
                planilla_numero TEXT DEFAULT 'S/N',
                estado TEXT DEFAULT 'ABIERTA', -- 'ABIERTA' o 'CERRADA'
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES usuarios (telegram_id)
            )
        """)
        
        # Migraciones automáticas para columnas nuevas en comisiones
        cursor.execute("PRAGMA table_info(comisiones)")
        cols_com = [c[1] for c in cursor.fetchall()]
        for col, tipo in [
            ("fecha_resolucion", "TEXT DEFAULT ''"),
            ("fechas_viaje_texto", "TEXT DEFAULT ''"),
            ("nota_pago", "TEXT DEFAULT 'S/N'"),
            ("exp_siaf", "TEXT DEFAULT 'S/N'"),
            ("fte_fto", "TEXT DEFAULT 'RDR'"),
            ("planilla_numero", "TEXT DEFAULT 'S/N'")
        ]:
            if col not in cols_com:
                cursor.execute(f"ALTER TABLE comisiones ADD COLUMN {col} {tipo}")
        
        # Tabla de Comprobantes de Pago / Gastos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comprobantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comision_id INTEGER NOT NULL,
                tipo_comprobante TEXT NOT NULL, -- 'Factura', 'Boleta', 'Ticket', 'Declaración Jurada', 'Pasaje'
                serie_numero TEXT,
                ruc TEXT,
                razon_social TEXT,
                nombre_comercial TEXT DEFAULT '',
                monto REAL NOT NULL,
                fecha_emision TEXT,
                concepto TEXT, -- 'Alimentación', 'Hospedaje', 'Movilidad', 'Otros'
                lugar TEXT DEFAULT '',
                estado_sunat TEXT,
                condicion_sunat TEXT,
                actividad_economica TEXT,
                alerta_sunat TEXT,
                foto_path TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (comision_id) REFERENCES comisiones (id)
            )
        """)

        # Migración automática si las columnas 'lugar' o 'nombre_comercial' no existen
        cursor.execute("PRAGMA table_info(comprobantes)")
        columnas = [col[1] for col in cursor.fetchall()]
        if "lugar" not in columnas:
            cursor.execute("ALTER TABLE comprobantes ADD COLUMN lugar TEXT DEFAULT ''")
        if "nombre_comercial" not in columnas:
            cursor.execute("ALTER TABLE comprobantes ADD COLUMN nombre_comercial TEXT DEFAULT ''")

        # Tabla de Caché SUNAT
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_sunat (
                ruc TEXT PRIMARY KEY,
                razon_social TEXT,
                estado TEXT,
                condicion TEXT,
                actividad_economica TEXT,
                direccion TEXT,
                fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# --- Funciones de Usuarios y Perfil ---

def registrar_o_actualizar_usuario(telegram_id: int, nombre: str, dni: str = ""):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (telegram_id, nombre, dni)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                nombre = excluded.nombre,
                dni = CASE WHEN excluded.dni != '' THEN excluded.dni ELSE usuarios.dni END
        """, (telegram_id, nombre, dni))
        conn.commit()

def actualizar_perfil_completo(telegram_id: int, nombre: str, dni: str, celular: str,
                                tipo_personal: str, dependencia_facultad: str, correo_institucional: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (telegram_id, nombre, dni, celular, tipo_personal, dependencia_facultad, correo_institucional)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                nombre = excluded.nombre,
                dni = excluded.dni,
                celular = excluded.celular,
                tipo_personal = excluded.tipo_personal,
                dependencia_facultad = excluded.dependencia_facultad,
                correo_institucional = excluded.correo_institucional
        """, (telegram_id, nombre, dni, celular, tipo_personal, dependencia_facultad, correo_institucional))
        conn.commit()

def obtener_usuario(telegram_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- Funciones de Comisiones ---

def crear_comision(telegram_id: int, numero_resolucion: str, destino: str, monto_asignado: float, 
                   fecha_resolucion: str = "", fechas_viaje_texto: str = "", fecha_inicio: str = "", 
                   fecha_fin: str = "", nota_pago: str = "S/N", exp_siaf: str = "S/N", 
                   fte_fto: str = "RDR", planilla_numero: str = "S/N") -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO comisiones (
                telegram_id, numero_resolucion, fecha_resolucion, destino,
                fechas_viaje_texto, monto_asignado, fecha_inicio, fecha_fin,
                nota_pago, exp_siaf, fte_fto, planilla_numero
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, numero_resolucion, fecha_resolucion, destino,
              fechas_viaje_texto, monto_asignado, fecha_inicio, fecha_fin,
              nota_pago, exp_siaf, fte_fto, planilla_numero))
        conn.commit()
        return cursor.lastrowid

def obtener_comision_activa(telegram_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM comisiones
            WHERE telegram_id = ? AND estado = 'ABIERTA'
            ORDER BY id DESC LIMIT 1
        """, (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def obtener_comision_por_id(comision_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM comisiones WHERE id = ?", (comision_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def cerrar_comision(comision_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE comisiones SET estado = 'CERRADA' WHERE id = ?
        """, (comision_id,))
        conn.commit()

# --- Funciones de Comprobantes ---

def registrar_comprobante(comision_id: int, tipo_comprobante: str, monto: float, 
                          serie_numero: str = "", ruc: str = "", razon_social: str = "", 
                          nombre_comercial: str = "", fecha_emision: str = "", concepto: str = "Alimentación", 
                          lugar: str = "", estado_sunat: str = "", condicion_sunat: str = "", 
                          actividad_economica: str = "", alerta_sunat: str = "", 
                          foto_path: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO comprobantes (
                comision_id, tipo_comprobante, serie_numero, ruc, razon_social,
                nombre_comercial, monto, fecha_emision, concepto, lugar, 
                estado_sunat, condicion_sunat, actividad_economica, alerta_sunat, foto_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (comision_id, tipo_comprobante, serie_numero, ruc, razon_social,
              nombre_comercial, monto, fecha_emision, concepto, lugar, 
              estado_sunat, condicion_sunat, actividad_economica, alerta_sunat, foto_path))
        conn.commit()
        return cursor.lastrowid

def obtener_resumen_gastos(comision_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM comprobantes WHERE comision_id = ?", (comision_id,))
        total_gastado = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM comprobantes WHERE comision_id = ?", (comision_id,))
        total_items = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT concepto, COALESCE(SUM(monto), 0) as total, COUNT(*) as cantidad
            FROM comprobantes
            WHERE comision_id = ?
            GROUP BY concepto
        """, (comision_id,))
        conceptos = [dict(r) for r in cursor.fetchall()]
        
        return {
            "total_gastado": float(total_gastado),
            "total_items": total_items,
            "por_concepto": conceptos
        }

def listar_comprobantes(comision_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM comprobantes
            WHERE comision_id = ?
            ORDER BY id ASC
        """, (comision_id,))
        return [dict(r) for r in cursor.fetchall()]

def verificar_comprobante_duplicado(comision_id: int, ruc: str, serie_numero: str, monto: float, fecha_emision: str = "") -> Optional[Dict[str, Any]]:
    """
    Verifica si un comprobante ya fue registrado previamente en la comisión activa.
    1. Comprueba por combinación única de RUC y Serie-Número (ej. 20601234567 + B001-00045).
    2. Comprueba por coincidencia exacta de RUC + Monto idéntico + Fecha de emisión.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Chequeo por RUC y Serie/Número
        if ruc and serie_numero and len(serie_numero.strip()) >= 3 and serie_numero.strip() != "S/N":
            serie_limpia = serie_numero.replace(" ", "").lower()
            cursor.execute("""
                SELECT * FROM comprobantes
                WHERE comision_id = ? AND ruc = ? AND LOWER(REPLACE(serie_numero, ' ', '')) = ?
                LIMIT 1
            """, (comision_id, ruc, serie_limpia))
            row = cursor.fetchone()
            if row:
                return dict(row)
                
        # 2. Chequeo por RUC, Monto y Fecha
        if ruc and monto > 0 and fecha_emision:
            cursor.execute("""
                SELECT * FROM comprobantes
                WHERE comision_id = ? AND ruc = ? AND ABS(monto - ?) < 0.01 AND fecha_emision = ?
                LIMIT 1
            """, (comision_id, ruc, monto, fecha_emision))
            row = cursor.fetchone()
            if row:
                return dict(row)
                
        return None

# --- Funciones de Caché SUNAT ---

def obtener_cache_sunat(ruc: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cache_sunat WHERE ruc = ?", (ruc,))
        row = cursor.fetchone()
        return dict(row) if row else None

def guardar_cache_sunat(ruc: str, razon_social: str, estado: str, condicion: str, actividad_economica: str = "", direccion: str = ""):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cache_sunat (ruc, razon_social, estado, condicion, actividad_economica, direccion)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ruc) DO UPDATE SET
                razon_social = excluded.razon_social,
                estado = excluded.estado,
                condicion = excluded.condicion,
                actividad_economica = excluded.actividad_economica,
                direccion = excluded.direccion,
                fecha_consulta = CURRENT_TIMESTAMP
        """, (ruc, razon_social, estado, condicion, actividad_economica, direccion))
        conn.commit()

def obtener_comprobante_por_id(comprobante_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM comprobantes WHERE id = ?", (comprobante_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def eliminar_comprobante(comprobante_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comprobantes WHERE id = ?", (comprobante_id,))
        conn.commit()
        return cursor.rowcount > 0

def actualizar_comprobante(comprobante_id: int, concepto: str, monto: float, lugar: str = "", nombre_comercial: str = "") -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE comprobantes 
            SET concepto = ?, monto = ?, lugar = ?, nombre_comercial = ?
            WHERE id = ?
        """, (concepto, monto, lugar, nombre_comercial, comprobante_id))
        conn.commit()
        return cursor.rowcount > 0

if __name__ == "__main__":
    init_db()
    print("Base de datos y migraciones completadas.")
