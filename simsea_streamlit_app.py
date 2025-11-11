# simsea_streamlit_app.py
"""
SIMSEA - Formulario público y panel admin en Streamlit
- Agregado: Usuario y contraseña en sidebar (usuario obligatorio para enviar)
- La contraseña del usuario se guarda hashed (SHA-256) si se proporciona.
- Logotipo integrado (logo_fundacion_small.png opcional)
- Conexión SQLite (configurable con SIMSEA_DATA_DIR y SIMSEA_DB_PATH)
- Exportación a Excel en memoria
"""

import streamlit as st
import sqlite3
import pandas as pd
import io
import os
import hashlib
from datetime import datetime, date

# ---------------------------
# Configuración inicial
# ---------------------------
st.set_page_config(page_title="FUNDACIÓN CUENCAS SAGRADAS", layout="wide")

# Estilos: fondo verde claro y café
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #e8f6ea 0%, #f2efe7 100%);
    }
    [data-testid="stSidebar"] {
        background-color: #d2b48c;
    }
    .header-box {
        background: linear-gradient(90deg, rgba(88,106,52,0.06), rgba(146,91,65,0.06));
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 12px;
    }
    .subtitle {font-size:14px; color:#8b4513}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# SIDEBAR: Usuario que ingresa datos (parte superior izquierda)
# ---------------------------
st.sidebar.header("Usuario (para ingresar datos)")
input_usuario = st.sidebar.text_input("Usuario", value="", help="Nombre o identificador del usuario que registra el proyecto")
input_password = st.sidebar.text_input("Contraseña (opcional)", type="password", help="(opcional) si la ingresas se guardará hashed (SHA-256)")

if input_usuario:
    st.sidebar.success(f"Usuario: {input_usuario}")
else:
    st.sidebar.info("Ingrese su usuario antes de enviar un proyecto")

# ---------------------------
# Mostrar logotipo y encabezado (centrado)
# ---------------------------
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    try:
        st.image("logo_fundacion_small.png", width=140)
    except Exception:
        try:
            st.image("logo_fundacion.png", width=180)
        except Exception:
            pass
    st.markdown(
        "<div class='header-box'><h1 style='text-align:center; color:#2e5c1e; margin:0;'>FUNDACIÓN CUENCAS SAGRADAS</h1>"
        "<div class='subtitle' style='text-align:center;'>Sistema Indígena de Monitoreo, Seguimiento, Evaluación y Aprendizaje</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ---------------------------
# Rutas y conexión DB
# ---------------------------
DATA_DIR = os.getenv("SIMSEA_DATA_DIR", ".")
DB_FILENAME = os.getenv("SIMSEA_DB_PATH", "SIMSEA.db")
DB_PATH = DB_FILENAME if os.path.isabs(DB_FILENAME) else os.path.join(DATA_DIR, DB_FILENAME)
ADMIN_PASSWORD = os.getenv("SIMSEA_ADMIN_PASSWORD", "admin")

# Crear carpeta de datos si no existe
try:
    if DATA_DIR and not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    pass

# Conexión SQLite robusta
conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30, isolation_level=None)
cur = conn.cursor()

# Crear tabla si no existe (agregadas columnas usuario y usuario_password)
cur.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    usuario TEXT,
    usuario_password TEXT,
    nombre_proyecto TEXT,
    pais_intervencion TEXT,
    provincia_departamento TEXT,
    canton_distrito TEXT,
    pueblo_nacionalidad TEXT,
    latitud REAL,
    longitud REAL,
    beneficiarios_hombres INTEGER,
    beneficiarios_mujeres INTEGER,
    beneficiarios_glbti INTEGER,
    total_beneficiarios INTEGER,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    duracion_dias INTEGER,
    monto_total REAL,
    fuente_financiamiento TEXT,
    entidad_ejecutora TEXT,
    eje_plan_biorregional TEXT,
    eje_tematico_plan_biorregional TEXT,
    estrategia_plan_biorregional TEXT,
    accion_plan_biorregional TEXT,
    objetivo_estrategico_pei TEXT,
    estrategia_pei TEXT,
    indicador_pb TEXT,
    unidad_medida_pb TEXT,
    meta_pb REAL,
    indicador_pei TEXT,
    unidad_medida_pei TEXT,
    meta_pei REAL,
    indicador_proyecto TEXT,
    unidad_medida_proyecto TEXT,
    meta_proyecto REAL,
    tendencia_indicador TEXT,
    anio_cumplimiento_meta INTEGER,
    anio_linea_base INTEGER,
    valor_linea_base REAL,
    meta_2021 REAL, meta_2022 REAL, meta_2023 REAL, meta_2024 REAL, meta_2025 REAL,
    meta_2026 REAL, meta_2027 REAL, meta_2028 REAL, meta_2029 REAL, meta_2030 REAL,
    total_meta_cumplida_acumulada REAL,
    porc_ejecucion_fisica REAL,
    presupuesto_programado_total REAL,
    presupuesto_devengado_total REAL,
    porc_ejecucion_presupuestaria REAL,
    prog_trimestre_2021 TEXT,
    meta_plan_1 REAL, meta_cum_1 REAL, pct_cum_1 REAL, pres_prog_1 REAL, pres_dev_1 REAL, pct_pres_1 REAL,
    meta_plan_2 REAL, meta_cum_2 REAL, pct_cum_2 REAL, pres_prog_2 REAL, pres_dev_2 REAL, pct_pres_2 REAL,
    meta_plan_3 REAL, meta_cum_3 REAL, pct_cum_3 REAL, pres_prog_3 REAL, pres_dev_3 REAL, pct_pres_3 REAL,
    meta_plan_4 REAL, meta_cum_4 REAL, pct_cum_4 REAL, pres_prog_4 REAL, pres_dev_4 REAL, pct_pres_4 REAL,
    meta_plan_anual REAL, meta_cum_anual REAL, pct_ejec_fis_anual REAL, pres_prog_anual REAL, pres_dev_anual REAL, pct_pres_anual REAL,
    nudos_criticos TEXT,
    logros_relevantes TEXT,
    aprendizajes TEXT,
    medios_de_verificacion TEXT,
    nombre_responsable TEXT,
    cargo_responsable TEXT,
    correo_responsable TEXT,
    telefono_responsable TEXT
);
""")
conn.commit()

# ---------------------------
# Utilidades
# ---------------------------
def percent(numerator, denominator):
    try:
        if denominator is None:
            return None
        denominator = float(denominator)
        if denominator == 0:
            return None
        return round(100.0 * float(numerator) / denominator, 2)
    except Exception:
        return None

def display_pct(v):
    return f"{v:.2f}%" if (v is not None) else "N/A"

def hash_password(plain):
    if not plain:
        return None
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()

# ---------------------------
# Formulario público
# ---------------------------
st.header("Formulario de ingreso información de proyectos")

with st.form(key="project_form", clear_on_submit=True):
    # Organizar inputs en 3 columnas
    c1, c2, c3 = st.columns([1,1,1])

    with c1:
        nombre_proyecto = st.text_input("Nombre del proyecto")
        pais_intervencion = st.selectbox("País de intervención", ["Ecuador", "Perú", "Biorregional: Ecuador – Perú"])
        provincia_departamento = st.selectbox("Provincia / departamento", [
            "Sucumbíos", "Orellana", "Napo", "Pastaza", "Morona Santiago", "Zamora Chinchipe",
            "Loreto", "Ucayali", "Madre de Dios", "San Martín", "Amazonas", "Huánuco", "Pasco", "Junín", "Cusco", "Ayacucho"
        ])
        canton_distrito = st.text_input("Cantón / distrito")
        pueblo_nacionalidad = st.text_input("Pueblo / nacionalidad")
        latitud = st.number_input("Coordenadas latitud (Y)", format="%.6f", value=0.0)
        longitud = st.number_input("Coordenadas longitud (X)", format="%.6f", value=0.0)
        beneficiarios_hombres = st.number_input("Beneficiarios hombres", min_value=0, value=0)
        beneficiarios_mujeres = st.number_input("Beneficiarios mujeres", min_value=0, value=0)
        beneficiarios_glbti = st.number_input("Beneficiarios GLBTI", min_value=0, value=0)

    with c2:
        monto_total = st.number_input("Monto total del proyecto", min_value=0.0, value=0.0, format="%.2f")
        fuente_financiamiento = st.text_input("Fuente de financiamiento")
        entidad_ejecutora = st.text_input("Entidad ejecutora")
        eje_plan_biorregional = st.text_input("Eje Plan Biorregional")
        eje_tematico_plan_biorregional = st.text_input("Eje temático Plan Biorregional")
        estrategia_plan_biorregional = st.text_input("Estrategia Plan Biorregional")
        accion_plan_biorregional = st.text_input("Acción Plan Biorregional")
        objetivo_estrategico_pei = st.text_input("Objetivo estratégico PEI")
        estrategia_pei = st.text_input("Estrategia PEI")
        indicador_pb = st.text_input("Indicador PB")
        unidad_medida_pb = st.text_input("Unidad de medida PB")
        meta_pb = st.number_input("Meta PB", value=0.0)

    with c3:
        indicador_pei = st.text_input("Indicador PEI")
        unidad_medida_pei = st.text_input("Unidad de medida PEI")
        meta_pei = st.number_input("Meta PEI", value=0.0)
        indicador_proyecto = st.text_input("Indicador del proyecto")
        unidad_medida_proyecto = st.text_input("Unidad de medida del proyecto")
        meta_proyecto = st.number_input("Meta del proyecto", value=0.0)
        tendencia_indicador = st.selectbox("Tendencia del indicador", ["Creciente", "Decreciente", "Horizontal"])
        anio_cumplimiento_meta = st.number_input("Año de cumplimiento de la meta", min_value=1900, max_value=2100, value=2025)
        anio_linea_base = st.number_input("Año de la línea base", min_value=1900, max_value=2100, value=2020)
        valor_linea_base = st.number_input("Valor de la línea base", value=0.0)

    st.markdown("---")
    st.markdown("#### Metas anualizadas (2021 - 2030)")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        meta_2021 = st.number_input("Meta 2021", value=0.0, key="m2021")
        meta_2026 = st.number_input("Meta 2026", value=0.0, key="m2026")
    with m2:
        meta_2022 = st.number_input("Meta 2022", value=0.0, key="m2022")
        meta_2027 = st.number_input("Meta 2027", value=0.0, key="m2027")
    with m3:
        meta_2023 = st.number_input("Meta 2023", value=0.0, key="m2023")
        meta_2028 = st.number_input("Meta 2028", value=0.0, key="m2028")
    with m4:
        meta_2024 = st.number_input("Meta 2024", value=0.0, key="m2024")
        meta_2029 = st.number_input("Meta 2029", value=0.0, key="m2029")
    with m5:
        meta_2025 = st.number_input("Meta 2025", value=0.0, key="m2025")
        meta_2030 = st.number_input("Meta 2030", value=0.0, key="m2030")

    st.markdown("---")
    col4, col5 = st.columns([1,1])
    with col4:
        total_meta_cumplida_acumulada = st.number_input("Total meta cumplida acumulada", value=0.0)
        presupuesto_programado_total = st.number_input("Presupuesto programado total", value=0.0)
        presupuesto_devengado_total = st.number_input("Presupuesto devengado total", value=0.0)
    with col5:
        st.markdown("**Programación trimestral (valores por trimestre)**")
        meta_plan_1 = st.number_input("Meta planificada 1T", value=0.0)
        meta_cum_1 = st.number_input("Meta cumplida 1T", value=0.0)
        pres_prog_1 = st.number_input("Pres. programado 1T", value=0.0)
        pres_dev_1 = st.number_input("Pres. devengado 1T", value=0.0)

        meta_plan_2 = st.number_input("Meta planificada 2T", value=0.0)
        meta_cum_2 = st.number_input("Meta cumplida 2T", value=0.0)
        pres_prog_2 = st.number_input("Pres. programado 2T", value=0.0)
        pres_dev_2 = st.number_input("Pres. devengado 2T", value=0.0)

        meta_plan_3 = st.number_input("Meta planificada 3T", value=0.0)
        meta_cum_3 = st.number_input("Meta cumplida 3T", value=0.0)
        pres_prog_3 = st.number_input("Pres. programado 3T", value=0.0)
        pres_dev_3 = st.number_input("Pres. devengado 3T", value=0.0)

        meta_plan_4 = st.number_input("Meta planificada 4T", value=0.0)
        meta_cum_4 = st.number_input("Meta cumplida 4T", value=0.0)
        pres_prog_4 = st.number_input("Pres. programado 4T", value=0.0)
        pres_dev_4 = st.number_input("Pres. devengado 4T", value=0.0)

    st.markdown("---")
    nudos_criticos = st.text_area("Nudos críticos")
    logros_relevantes = st.text_area("Logros relevantes")
    aprendizajes = st.text_area("Aprendizajes")
    medios_de_verificacion = st.text_area("Medios de verificación")

    nombre_responsable = st.text_input("Nombre del responsable del proyecto")
    cargo_responsable = st.text_input("Cargo del responsable del proyecto")
    correo_responsable = st.text_input("Correo del responsable del proyecto")
    telefono_responsable = st.text_input("Teléfono del responsable del proyecto")

    # Fecha inicio / fin y cálculos (asegurar que estén definidos antes de usarlos)
    fecha_inicio = st.date_input("Fecha de inicio", value=date.today())
    fecha_fin = st.date_input("Fecha de finalización", value=date.today())
    duracion_dias = (fecha_fin - fecha_inicio).days if (fecha_fin and fecha_inicio) else 0

    # Cálculos dinámicos (previos al envío)
    total_beneficiarios = int(beneficiarios_hombres) + int(beneficiarios_mujeres) + int(beneficiarios_glbti)
    porc_ejecucion_fisica = percent(total_meta_cumplida_acumulada, meta_proyecto)
    porc_ejec_pres = percent(presupuesto_devengado_total, presupuesto_programado_total)
    meta_plan_anual = meta_plan_1 + meta_plan_2 + meta_plan_3 + meta_plan_4
    meta_cum_anual = meta_cum_1 + meta_cum_2 + meta_cum_3 + meta_cum_4
    pct_ejec_fis_anual = percent(meta_cum_anual, meta_plan_anual)
    pres_prog_anual = pres_prog_1 + pres_prog_2 + pres_prog_3 + pres_prog_4
    pres_dev_anual = pres_dev_1 + pres_dev_2 + pres_dev_3 + pres_dev_4
    pct_pres_anual = percent(pres_dev_anual, pres_prog_anual)

    # Mostrar métricas dinámicas
    mm1, mm2, mm3, mm4 = st.columns(4)
    mm1.metric("Total beneficiarios", f"{total_beneficiarios:,}")
    mm2.metric("Duración (días)", f"{duracion_dias}")
    mm3.metric("Ejecución física (proyecto)", display_pct(porc_ejecucion_fisica))
    mm4.metric("Ejecución presup. (proyecto)", display_pct(porc_ejec_pres))

    aa1, aa2, aa3 = st.columns(3)
    aa1.metric("Meta plan anual", f"{meta_plan_anual:.2f}")
    aa2.metric("Meta cumplida anual", f"{meta_cum_anual:.2f}")
    aa3.metric("% ejecución física anual", display_pct(pct_ejec_fis_anual))

    bb1, bb2, bb3 = st.columns(3)
    bb1.metric("Pres. programado anual", f"{pres_prog_anual:.2f}")
    bb2.metric("Pres. devengado anual", f"{pres_dev_anual:.2f}")
    bb3.metric("% ejecución presup. anual", display_pct(pct_pres_anual))

    # Botón enviar
    submit = st.form_submit_button("Enviar proyecto")

    # Al enviar desde dentro del form
    if submit:
        # Validar que haya un usuario antes de guardar
        if not input_usuario or input_usuario.strip() == "":
            st.error("Debe ingresar su Usuario en la barra lateral antes de enviar el proyecto.")
        else:
            created_at = datetime.utcnow().isoformat()
            usuario_hashed = hash_password(input_password)

            # Recalcular por seguridad
            total_beneficiarios = int(beneficiarios_hombres) + int(beneficiarios_mujeres) + int(beneficiarios_glbti)
            duracion_dias = (fecha_fin - fecha_inicio).days if (fecha_fin and fecha_inicio) else 0
            porc_ejecucion_fisica = percent(total_meta_cumplida_acumulada, meta_proyecto)
            porc_ejec_pres = percent(presupuesto_devengado_total, presupuesto_programado_total)
            meta_plan_anual = meta_plan_1 + meta_plan_2 + meta_plan_3 + meta_plan_4
            meta_cum_anual = meta_cum_1 + meta_cum_2 + meta_cum_3 + meta_cum_4
            pct_ejec_fis_anual = percent(meta_cum_anual, meta_plan_anual)
            pres_prog_anual = pres_prog_1 + pres_prog_2 + pres_prog_3 + pres_prog_4
            pres_dev_anual = pres_dev_1 + pres_dev_2 + pres_dev_3 + pres_dev_4
            pct_pres_anual = percent(pres_dev_anual, pres_prog_anual)

            # Preparar registro (diccionario)
            row = {
                "created_at": created_at,
                "usuario": input_usuario,
                "usuario_password": usuario_hashed,
                "nombre_proyecto": nombre_proyecto,
                "pais_intervencion": pais_intervencion,
                "provincia_departamento": provincia_departamento,
                "canton_distrito": canton_distrito,
                "pueblo_nacionalidad": pueblo_nacionalidad,
                "latitud": latitud,
                "longitud": longitud,
                "beneficiarios_hombres": beneficiarios_hombres,
                "beneficiarios_mujeres": beneficiarios_mujeres,
                "beneficiarios_glbti": beneficiarios_glbti,
                "total_beneficiarios": total_beneficiarios,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat(),
                "duracion_dias": duracion_dias,
                "monto_total": monto_total,
                "fuente_financiamiento": fuente_financiamiento,
                "entidad_ejecutora": entidad_ejecutora,
                "eje_plan_biorregional": eje_plan_biorregional,
                "eje_tematico_plan_biorregional": eje_tematico_plan_biorregional,
                "estrategia_plan_biorregional": estrategia_plan_biorregional,
                "accion_plan_biorregional": accion_plan_biorregional,
                "objetivo_estrategico_pei": objetivo_estrategico_pei,
                "estrategia_pei": estrategia_pei,
                "indicador_pb": indicador_pb,
                "unidad_medida_pb": unidad_medida_pb,
                "meta_pb": meta_pb,
                "indicador_pei": indicador_pei,
                "unidad_medida_pei": unidad_medida_pei,
                "meta_pei": meta_pei,
                "indicador_proyecto": indicador_proyecto,
                "unidad_medida_proyecto": unidad_medida_proyecto,
                "meta_proyecto": meta_proyecto,
                "tendencia_indicador": tendencia_indicador,
                "anio_cumplimiento_meta": anio_cumplimiento_meta,
                "anio_linea_base": anio_linea_base,
                "valor_linea_base": valor_linea_base,
                "meta_2021": meta_2021,
                "meta_2022": meta_2022,
                "meta_2023": meta_2023,
                "meta_2024": meta_2024,
                "meta_2025": meta_2025,
                "meta_2026": meta_2026,
                "meta_2027": meta_2027,
                "meta_2028": meta_2028,
                "meta_2029": meta_2029,
                "meta_2030": meta_2030,
                "total_meta_cumplida_acumulada": total_meta_cumplida_acumulada,
                "porc_ejecucion_fisica": porc_ejecucion_fisica,
                "presupuesto_programado_total": presupuesto_programado_total,
                "presupuesto_devengado_total": presupuesto_devengado_total,
                "porc_ejecucion_presupuestaria": porc_ejec_pres,
                "prog_trimestre_2021": None,
                "meta_plan_1": meta_plan_1, "meta_cum_1": meta_cum_1, "pct_cum_1": percent(meta_cum_1, meta_plan_1), "pres_prog_1": pres_prog_1, "pres_dev_1": pres_dev_1, "pct_pres_1": percent(pres_dev_1, pres_prog_1),
                "meta_plan_2": meta_plan_2, "meta_cum_2": meta_cum_2, "pct_cum_2": percent(meta_cum_2, meta_plan_2), "pres_prog_2": pres_prog_2, "pres_dev_2": pres_dev_2, "pct_pres_2": percent(pres_dev_2, pres_prog_2),
                "meta_plan_3": meta_plan_3, "meta_cum_3": meta_cum_3, "pct_cum_3": percent(meta_cum_3, meta_plan_3), "pres_prog_3": pres_prog_3, "pres_dev_3": pres_dev_3, "pct_pres_3": percent(pres_dev_3, pres_prog_3),
                "meta_plan_4": meta_plan_4, "meta_cum_4": meta_cum_4, "pct_cum_4": percent(meta_cum_4, meta_plan_4), "pres_prog_4": pres_prog_4, "pres_dev_4": pres_dev_4, "pct_pres_4": percent(pres_dev_4, pres_prog_4),
                "meta_plan_anual": meta_plan_anual, "meta_cum_anual": meta_cum_anual, "pct_ejec_fis_anual": pct_ejec_fis_anual, "pres_prog_anual": pres_prog_anual, "pres_dev_anual": pres_dev_anual, "pct_pres_anual": pct_pres_anual,
                "nudos_criticos": nudos_criticos, "logros_relevantes": logros_relevantes, "aprendizajes": aprendizajes, "medios_de_verificacion": medios_de_verificacion,
                "nombre_responsable": nombre_responsable, "cargo_responsable": cargo_responsable, "correo_responsable": correo_responsable, "telefono_responsable": telefono_responsable
            }

            # Inserción dinámica
            cols = ','.join(row.keys())
            placeholders = ','.join(['?'] * len(row))
            values = tuple(row.values())

            try:
                cur.execute(f"INSERT INTO projects ({cols}) VALUES ({placeholders})", values)
                conn.commit()
                st.success("✅ Proyecto guardado correctamente.")
            except Exception as e:
                st.error(f"Error al guardar en la base de datos: {e}")

# ---------------------------
# Panel de administración
# ---------------------------
st.sidebar.header("Administración")
pwd = st.sidebar.text_input("Contraseña admin", type="password")
if pwd == ADMIN_PASSWORD:
    st.sidebar.success("Acceso concedido")
    st.header("Panel de administración")

    try:
        df = pd.read_sql_query("SELECT * FROM projects ORDER BY created_at DESC", conn)
    except Exception as e:
        st.error(f"Error leyendo la base de datos: {e}")
        df = pd.DataFrame()

    st.subheader(f"Registros: {len(df)}")

    # Filtros simples
    with st.expander("Filtros"):
        filtro_pueblo = st.text_input("Filtrar por pueblo / nacionalidad")
        filtro_pais = st.selectbox("Filtrar por país", ["", "Ecuador", "Perú", "Biorregional: Ecuador – Perú"])
        if filtro_pueblo and 'pueblo_nacionalidad' in df.columns:
            df = df[df['pueblo_nacionalidad'].astype(str).str.contains(filtro_pueblo, case=False, na=False)]
        if filtro_pais and 'pais_intervencion' in df.columns and filtro_pais:
            df = df[df['pais_intervencion'] == filtro_pais]

    # Mostrar la columna 'usuario' para saber quién ingresó cada registro
    if 'usuario' in df.columns:
        st.markdown("**Columna `usuario`:** identifica quién envió el registro (contraseña almacenada hashed).")
    st.dataframe(df, use_container_width=True)

    # Exportar a Excel (en memoria)
    if not df.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="projects")
        buffer.seek(0)
        st.download_button(
            label="⬇️ Descargar Excel (registros filtrados)",
            data=buffer.getvalue(),
            file_name=f"simsea_projects_{datetime.now().date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Resumen rápido
    st.subheader("Resumen")
    if not df.empty:
        total_prog = pd.to_numeric(df.get('presupuesto_programado_total', pd.Series([0])), errors='coerce').fillna(0).sum()
        total_dev = pd.to_numeric(df.get('presupuesto_devengado_total', pd.Series([0])), errors='coerce').fillna(0).sum()
        st.metric("Total presupuestos programados", f"{total_prog:,.2f}")
        st.metric("Total presupuestos devengados", f"{total_dev:,.2f}")
else:
    if pwd:
        st.sidebar.error("Contraseña incorrecta. Verifique SIMSEA_ADMIN_PASSWORD.")
    else:
        st.sidebar.info("Ingrese la contraseña de administrador para ver el panel.")

# ---------------------------
# Fin
# ---------------------------
# - Cambia SIMSEA_ADMIN_PASSWORD en variables de entorno para producción.
# - Si vas a desplegar en Render/Railway, monta almacenamiento persistente y configura SIMSEA_DATA_DIR.
