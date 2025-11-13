# simsea_streamlit_app.py
"""
SIMSEA - Formulario completo con Guardar / Limpiar / Buscar / Actualizar / Eliminar
- Soporta admin (credenciales desde env) + registro libre de usuarios dentro de la app
- Manejo seguro de session_state con __pending_load__ y __do_reset__
- safe_rerun() intenta usar experimental_rerun() o rerun() según la versión
- Exporta a Excel y CSV
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
import hashlib
import re
import os
import io
import traceback

# --- Conexión Supabase usando la librería oficial ---
from supabase import create_client, Client
# --- Variables de conexión desde Secrets ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Prueba: listar registros de la tabla 'projects'
    response = supabase.table("projects").select("*").limit(1).execute()
    
    if response.data:
        st.success("✅ Conexión exitosa a la base de datos Supabase")
        st.write("Primer registro de la tabla 'projects' (si existe):", response.data)
    else:
        st.warning("⚠️ Conexión correcta, pero la tabla 'projects' está vacía o no existe.")
except Exception as e:
    st.error(f"❌ Error de conexión a Supabase: {e}")

# ---------------------------
# Config & helpers
# ---------------------------
st.set_page_config(page_title="FUNDACIÓN CUENCAS SAGRADAS - SIMSEA", layout="wide")

def safe_rerun():
    """Intenta recargar la app de forma segura con diferentes APIs de Streamlit."""
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
        elif hasattr(st, "rerun"):
            st.rerun()
        else:
            st.info("Por favor recarga la página manualmente para aplicar los cambios.")
    except Exception:
        try:
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.info("Por favor recarga la página manualmente para aplicar los cambios.")
        except Exception:
            st.info("Por favor recarga la página manualmente para aplicar los cambios.")

def hash_password(plain: str):
    return hashlib.sha256(plain.encode("utf-8")).hexdigest() if plain else None

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

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def is_valid_email(email: str):
    return bool(email and EMAIL_RE.match(email))

# ---------------------------
# CSS
# ---------------------------
st.markdown("""<style>
[data-testid="stAppViewContainer"] { background: linear-gradient(180deg,#e8f6ea 0%,#f7f3ed 100%); }
[data-testid="stSidebar"] { background-color: #d2b48c; }
.header-box { background: linear-gradient(90deg, rgba(88,106,52,0.06), rgba(146,91,65,0.06)); padding: 14px; border-radius: 12px; margin-bottom: 12px; border:1px solid rgba(120,90,60,0.06);}
.subtitle { font-size:14px; color:#8b4513; }
.stTextInput>div>div>input, .stNumberInput>div>div>input, .stTextArea>div>div>textarea, .stDateInput>div>div>input {
    background-color: #ffffff !important;
    border-radius: 8px !important;
    padding: 8px !important;
}
div.stButton > button { border-radius: 10px; padding: 8px 12px; }
</style>""", unsafe_allow_html=True)

# ---------------------------
# DB paths and admin credentials
# ---------------------------
DATA_DIR = os.getenv("SIMSEA_DATA_DIR", ".")
DB_FILENAME = os.getenv("SIMSEA_DB_PATH", "SIMSEA.db")
DB_PATH = DB_FILENAME if os.path.isabs(DB_FILENAME) else os.path.join(DATA_DIR, DB_FILENAME)

ADMIN_USER = os.getenv("SIMSEA_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("SIMSEA_ADMIN_PASSWORD", "admin")

# ensure data dir exists
if DATA_DIR and not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# --- Conexión a Supabase (PostgreSQL) ---
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT", "5432")

# --- Diagnóstico: mostrar credenciales leídas ---
st.write("🔍 Diagnóstico de conexión a Supabase")
st.write("DB_HOST:", DB_HOST)
st.write("DB_NAME:", DB_NAME)
st.write("DB_USER:", DB_USER)
st.write("DB_PASS:", "*****" if DB_PASS else "(vacío)")
st.write("DB_PORT:", DB_PORT)

# Crear motor SQLAlchemy (para pandas.read_sql_query)
DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

# Conexión principal con psycopg2
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    port=DB_PORT,
    sslmode="require"
)
conn.autocommit = False
cur = conn.cursor()

# ---------------------------
# Keys / defaults (session_state)
# ---------------------------
P = "simsea_"
years = list(range(2021, 2031))

SHORT_KEYS = [
    "sidebar_usuario", "sidebar_password",  # sidebar
    "edit_id", "__pending_load__", "__do_reset__", "pending_delete_id",  # control flags
    "nombre_proyecto","pais_intervencion","provincia_departamento","canton_distrito","pueblo_nacionalidad",
    "fecha_inicio","fecha_fin","latitud","longitud",
    "beneficiarios_hombres","beneficiarios_mujeres","beneficiarios_glbti",
    "monto_total","fuente_financiamiento","entidad_ejecutora",
    "eje_plan_biorregional","eje_tematico_plan_biorregional","estrategia_plan_biorregional","accion_plan_biorregional",
    "objetivo_estrategico_pei","estrategia_pei",
    "indicador_pb","unidad_medida_pb","meta_pb",
    "indicador_pei","unidad_medida_pei","meta_pei",
    "indicador_proyecto","unidad_medida_proyecto","meta_proyecto",
    "tendencia_indicador","anio_cumplimiento_meta","anio_linea_base","valor_linea_base",
    "total_meta_cumplida_acumulada","presupuesto_programado_total","presupuesto_devengado_total",
    "meta_plan_1","meta_cum_1","pres_prog_1","pres_dev_1",
    "meta_plan_2","meta_cum_2","pres_prog_2","pres_dev_2",
    "meta_plan_3","meta_cum_3","pres_prog_3","pres_dev_3",
    "meta_plan_4","meta_cum_4","pres_prog_4","pres_dev_4",
    "meta_plan_anual","meta_cum_anual","pres_prog_anual","pres_dev_anual",
    "nudos_criticos","logros_relevantes","aprendizajes","medios_de_verificacion",
    "nombre_responsable","cargo_responsable","correo_responsable","telefono_responsable",
    "search_id","filter_pueblo","filter_pais","filter_usuario"
]
for y in years:
    SHORT_KEYS.append(f"meta_{y}")

# defaults
DEFAULTS = {}
for k in SHORT_KEYS:
    if k in ("beneficiarios_hombres","beneficiarios_mujeres","beneficiarios_glbti","search_id"):
        DEFAULTS[k] = 0
    elif k in ("anio_cumplimiento_meta","anio_linea_base"):
        DEFAULTS[k] = date.today().year
    elif k.startswith("meta_") or k.startswith("meta_plan_") or k.startswith("meta_cum_") or k.startswith("pres_prog_") or k.startswith("pres_dev_") or k in ("monto_total","latitud","longitud","valor_linea_base","total_meta_cumplida_acumulada","presupuesto_programado_total","presupuesto_devengado_total"):
        DEFAULTS[k] = 0.0
    elif k in ("fecha_inicio","fecha_fin"):
        DEFAULTS[k] = date.today()
    elif k in ("sidebar_password",):
        DEFAULTS[k] = ""
    else:
        DEFAULTS[k] = ""

# initialize session_state keys
for k, v in DEFAULTS.items():
    if P + k not in st.session_state:
        st.session_state[P + k] = v

# ensure control flags exist
if P + "__pending_load__" not in st.session_state:
    st.session_state[P + "__pending_load__"] = None
if P + "__do_reset__" not in st.session_state:
    st.session_state[P + "__do_reset__"] = False
if P + "edit_id" not in st.session_state:
    st.session_state[P + "edit_id"] = None
if P + "pending_delete_id" not in st.session_state:
    st.session_state[P + "pending_delete_id"] = None

# Apply pending reset/load BEFORE widgets (important)
if st.session_state.get(P + "__do_reset__", False):
    for k in SHORT_KEYS:
        st.session_state[P + k] = DEFAULTS[k]
    st.session_state[P + "edit_id"] = None
    st.session_state[P + "pending_delete_id"] = None
    st.session_state[P + "__do_reset__"] = False

if st.session_state.get(P + "__pending_load__"):
    payload = st.session_state[P + "__pending_load__"]
    # payload is dict short_key->value and optional "_edit_id_"
    for k, val in payload.items():
        if k == "_edit_id_":
            st.session_state[P + "edit_id"] = val
        elif P + k in st.session_state:
            st.session_state[P + k] = val
    st.session_state[P + "__pending_load__"] = None

# ---------------------------
# Sidebar: usuario y admin login + registro
# ---------------------------
st.sidebar.header("Acceso")
# Admin login (env or custom)
st.sidebar.markdown("**Acceso administrador (opcional)**")
admin_user_input = st.sidebar.text_input("Admin usuario", value="", key="__admin_user_input")
admin_pwd_input = st.sidebar.text_input("Admin contraseña", type="password", key="__admin_pwd_input")

is_admin = False
if admin_user_input and admin_pwd_input:
    if admin_user_input == ADMIN_USER and admin_pwd_input == ADMIN_PASSWORD:
        is_admin = True
        st.sidebar.success("Acceso admin concedido")
    else:
        st.sidebar.error("Credenciales admin incorrectas")

# User login / register (app users)
st.sidebar.markdown("---")
st.sidebar.subheader("Usuario de la aplicación")
login_sel = st.sidebar.radio("¿Entrar o registrar?", ("Entrar", "Registrar"), index=0, key="__login_sel")

if login_sel == "Entrar":
    username_input = st.sidebar.text_input("Usuario", value=st.session_state.get(P + "sidebar_usuario", ""), key="__login_username")
    password_input = st.sidebar.text_input("Contraseña", type="password", key="__login_password")
    if st.sidebar.button("Iniciar sesión"):
        if not username_input or not password_input:
            st.sidebar.error("Ingrese usuario y contraseña.")
        else:
            cur.execute("SELECT password_hash FROM users WHERE username=%s", (username_input.strip(),))
            r = cur.fetchone()
            if r:
                stored = r[0]
                if stored == hash_password(password_input):
                    st.session_state[P + "sidebar_usuario"] = username_input.strip()
                    st.sidebar.success(f"Sesión iniciada como: {username_input.strip()}")
                else:
                    st.sidebar.error("Usuario o contraseña incorrectos.")
            else:
                st.sidebar.error("Usuario no existe. Regístrese primero.")
else:
    # Registrar
    new_user = st.sidebar.text_input("Nuevo usuario", value="", key="__reg_user")
    new_pwd = st.sidebar.text_input("Nueva contraseña", type="password", key="__reg_pwd")
    new_pwd2 = st.sidebar.text_input("Confirmar contraseña", type="password", key="__reg_pwd2")
    if st.sidebar.button("Registrar usuario"):
        if not new_user or not new_pwd:
            st.sidebar.error("Usuario y contraseña obligatorios.")
        elif new_pwd != new_pwd2:
            st.sidebar.error("Las contraseñas no coinciden.")
        else:
            try:
                cur.execute("INSERT INTO users (username, password_hash, created_at) VALUES (%s,%s,%s)",
                            (new_user.strip(), hash_password(new_pwd), datetime.utcnow().isoformat()))
                conn.commit()
                st.sidebar.success("Usuario registrado correctamente. Ahora puede iniciar sesión.")
            except psycopg2.IntegrityError:
                st.sidebar.error("El usuario ya existe. Elija otro nombre.")
            except Exception as e:
                st.sidebar.error(f"Error registro: {e}")

# Show current logged user hint
active_user = st.session_state.get(P + "sidebar_usuario", "")
if active_user:
    st.sidebar.info(f"Usuario activo: {active_user}")
else:
    st.sidebar.info("No hay usuario activo. Por favor inicie sesión o regístrese.")

st.sidebar.markdown("---")
st.sidebar.caption("Admin por defecto: setear SIMSEA_ADMIN_USER / SIMSEA_ADMIN_PASSWORD como variables de entorno en producción.")

# ---------------------------
# Header (logo + title)
# ---------------------------
col1, col2, col3 = st.columns([1,3,1])
with col2:
    try:
        st.image("logo_fundacion_small.png", width=140)
    except Exception:
        try:
            st.image("logo_fundacion.png", width=180)
        except Exception:
            pass
    st.markdown("<div class='header-box'><h1 style='text-align:center; color:#2e5c1e; margin:0;'>FUNDACIÓN CUENCAS SAGRADAS</h1>"
                "<div class='subtitle' style='text-align:center;'>Sistema Indígena de Monitoreo, Seguimiento, Evaluación y Aprendizaje</div></div>",
                unsafe_allow_html=True)
st.markdown("---")

# ---------------------------
# Form widgets
# ---------------------------
st.header("Formulario de ingreso / edición de proyectos")

c1, c2, c3 = st.columns([1,1,1])
with c1:
    nombre_proyecto = st.text_input("Nombre del proyecto", value=st.session_state[P + "nombre_proyecto"], key=P + "nombre_proyecto")
    pais_list = ["Ecuador","Perú","Biorregional: Ecuador – Perú"]
    pais_default = st.session_state[P + "pais_intervencion"] if st.session_state[P + "pais_intervencion"] in pais_list else pais_list[0]
    pais_intervencion = st.selectbox("País de intervención", pais_list, index=pais_list.index(pais_default), key=P + "pais_intervencion")
    provincias = [
        "Sucumbíos", "Orellana", "Napo", "Pastaza", "Morona Santiago", "Zamora Chinchipe",
        "Loreto", "Ucayali", "Madre de Dios", "San Martín", "Amazonas", "Huánuco", "Pasco", "Junín", "Cusco", "Ayacucho"
    ]
    # ensure default index exists
    try:
        prov_index = provincias.index(st.session_state[P + "provincia_departamento"]) if st.session_state[P + "provincia_departamento"] in provincias else 0
    except Exception:
        prov_index = 0
    provincia_departamento = st.selectbox("Provincia / departamento", provincias, index=prov_index, key=P + "provincia_departamento")
    canton_distrito = st.text_input("Cantón / distrito", value=st.session_state[P + "canton_distrito"], key=P + "canton_distrito")
    pueblo_nacionalidad = st.text_input("Pueblo / nacionalidad", value=st.session_state[P + "pueblo_nacionalidad"], key=P + "pueblo_nacionalidad")

    # fechas (ubicadas después de pueblo)
    fecha_inicio = st.date_input("Fecha de inicio", value=st.session_state[P + "fecha_inicio"], key=P + "fecha_inicio")
    fecha_fin = st.date_input("Fecha de finalización", value=st.session_state[P + "fecha_fin"], key=P + "fecha_fin")
    duracion_dias = (fecha_fin - fecha_inicio).days if (fecha_fin and fecha_inicio) else 0

with c2:
    latitud = st.number_input("Coordenadas geográficas latitud (Y)", format="%.6f", value=float(st.session_state[P + "latitud"] or 0.0), key=P + "latitud")
    longitud = st.number_input("Coordenadas geográficas longitud (X)", format="%.6f", value=float(st.session_state[P + "longitud"] or 0.0), key=P + "longitud")
    beneficiarios_hombres = st.number_input("Beneficiarios hombres", min_value=0, value=int(st.session_state[P + "beneficiarios_hombres"] or 0), key=P + "beneficiarios_hombres")
    beneficiarios_mujeres = st.number_input("Beneficiarios mujeres", min_value=0, value=int(st.session_state[P + "beneficiarios_mujeres"] or 0), key=P + "beneficiarios_mujeres")
    beneficiarios_glbti = st.number_input("Beneficiarios GLBTI", min_value=0, value=int(st.session_state[P + "beneficiarios_glbti"] or 0), key=P + "beneficiarios_glbti")
    monto_total = st.number_input("Monto total del proyecto", min_value=0.0, value=float(st.session_state[P + "monto_total"] or 0.0), format="%.2f", key=P + "monto_total")
    fuente_financiamiento = st.text_input("Fuente de financiamiento", value=st.session_state[P + "fuente_financiamiento"], key=P + "fuente_financiamiento")
    entidad_ejecutora = st.text_input("Entidad ejecutora", value=st.session_state[P + "entidad_ejecutora"], key=P + "entidad_ejecutora")

with c3:
    eje_plan_biorregional = st.text_input("Eje Plan Biorregional", value=st.session_state[P + "eje_plan_biorregional"], key=P + "eje_plan_biorregional")
    eje_tematico_plan_biorregional = st.text_input("Eje temático Plan Biorregional", value=st.session_state[P + "eje_tematico_plan_biorregional"], key=P + "eje_tematico_plan_biorregional")
    estrategia_plan_biorregional = st.text_input("Estrategia Plan Biorregional", value=st.session_state[P + "estrategia_plan_biorregional"], key=P + "estrategia_plan_biorregional")
    accion_plan_biorregional = st.text_input("Acción Plan Biorregional", value=st.session_state[P + "accion_plan_biorregional"], key=P + "accion_plan_biorregional")
    objetivo_estrategico_pei = st.text_input("Objetivo estratégico PEI", value=st.session_state[P + "objetivo_estrategico_pei"], key=P + "objetivo_estrategico_pei")
    estrategia_pei = st.text_input("Estrategia PEI", value=st.session_state[P + "estrategia_pei"], key=P + "estrategia_pei")

st.markdown("---")
# indicadores y metas
c4, c5, c6 = st.columns([1,1,1])
with c4:
    indicador_pb = st.text_input("Indicador PB", value=st.session_state[P + "indicador_pb"], key=P + "indicador_pb")
    unidad_medida_pb = st.text_input("Unidad de medida PB", value=st.session_state[P + "unidad_medida_pb"], key=P + "unidad_medida_pb")
    meta_pb = st.number_input("Meta PB", value=float(st.session_state[P + "meta_pb"] or 0.0), key=P + "meta_pb")
with c5:
    indicador_pei = st.text_input("Indicador PEI", value=st.session_state[P + "indicador_pei"], key=P + "indicador_pei")
    unidad_medida_pei = st.text_input("Unidad de medida PEI", value=st.session_state[P + "unidad_medida_pei"], key=P + "unidad_medida_pei")
    meta_pei = st.number_input("Meta PEI", value=float(st.session_state[P + "meta_pei"] or 0.0), key=P + "meta_pei")
with c6:
    indicador_proyecto = st.text_input("Indicador del proyecto", value=st.session_state[P + "indicador_proyecto"], key=P + "indicador_proyecto")
    unidad_medida_proyecto = st.text_input("Unidad de medida del proyecto", value=st.session_state[P + "unidad_medida_proyecto"], key=P + "unidad_medida_proyecto")
    meta_proyecto = st.number_input("Meta del proyecto", value=float(st.session_state[P + "meta_proyecto"] or 0.0), key=P + "meta_proyecto")
    tendencia_indicador = st.selectbox("Tendencia del indicador", ["Creciente","Decreciente","Horizontal"], index=0, key=P + "tendencia_indicador")
    anio_cumplimiento_meta = st.number_input("Año de cumplimiento de la meta", min_value=1900, max_value=2100,
                                            value=int(st.session_state[P + "anio_cumplimiento_meta"] or date.today().year),
                                            key=P + "anio_cumplimiento_meta")
    anio_linea_base = st.number_input("Año de la línea base", min_value=1900, max_value=2100,
                                     value=int(st.session_state[P + "anio_linea_base"] or date.today().year),
                                     key=P + "anio_linea_base")
    valor_linea_base = st.number_input("Valor de la línea base", value=float(st.session_state[P + "valor_linea_base"] or 0.0), key=P + "valor_linea_base")

st.markdown("---")
# metas anualizadas 2021-2030
for yr in years:
    st.number_input(f"Meta anualizada {yr}", value=float(st.session_state.get(P + f"meta_{yr}", 0.0) or 0.0), key=P + f"meta_{yr}")

st.markdown("---")
total_meta_cumplida_acumulada = st.number_input("Total meta cumplida acumulada", value=float(st.session_state[P + "total_meta_cumplida_acumulada"] or 0.0), key=P + "total_meta_cumplida_acumulada")
porc_ejecucion_fisica = percent(total_meta_cumplida_acumulada, meta_proyecto)
presupuesto_programado_total = st.number_input("Presupuesto programado total", value=float(st.session_state[P + "presupuesto_programado_total"] or 0.0), key=P + "presupuesto_programado_total")
presupuesto_devengado_total = st.number_input("Presupuesto devengado total", value=float(st.session_state[P + "presupuesto_devengado_total"] or 0.0), key=P + "presupuesto_devengado_total")
porc_ejecucion_presupuestaria = percent(presupuesto_devengado_total, presupuesto_programado_total)

st.markdown("---")
st.subheader("Programación trimestral (valores por trimestre)")
for t in range(1,5):
    st.number_input(f"Meta planificada {t}T", value=float(st.session_state[P + f"meta_plan_{t}"] or 0.0), key=P + f"meta_plan_{t}")
    st.number_input(f"Meta cumplida {t}T", value=float(st.session_state[P + f"meta_cum_{t}"] or 0.0), key=P + f"meta_cum_{t}")
    st.number_input(f"Presupuesto programado {t}T", value=float(st.session_state[P + f"pres_prog_{t}"] or 0.0), key=P + f"pres_prog_{t}")
    st.number_input(f"Presupuesto devengado {t}T", value=float(st.session_state[P + f"pres_dev_{t}"] or 0.0), key=P + f"pres_dev_{t}")

st.markdown("---")
nudos_criticos = st.text_area("Nudos críticos", value=st.session_state[P + "nudos_criticos"], key=P + "nudos_criticos")
logros_relevantes = st.text_area("Logros relevantes", value=st.session_state[P + "logros_relevantes"], key=P + "logros_relevantes")
aprendizajes = st.text_area("Aprendizajes", value=st.session_state[P + "aprendizajes"], key=P + "aprendizajes")
medios_de_verificacion = st.text_area("Medios de verificación", value=st.session_state[P + "medios_de_verificacion"], key=P + "medios_de_verificacion")

nombre_responsable = st.text_input("Nombre del responsable del proyecto", value=st.session_state[P + "nombre_responsable"], key=P + "nombre_responsable")
cargo_responsable = st.text_input("Cargo del responsable del proyecto", value=st.session_state[P + "cargo_responsable"], key=P + "cargo_responsable")
correo_responsable = st.text_input("Correo del responsable del proyecto", value=st.session_state[P + "correo_responsable"], key=P + "correo_responsable")
telefono_responsable = st.text_input("Teléfono del responsable del proyecto", value=st.session_state[P + "telefono_responsable"], key=P + "telefono_responsable")

# ---------------------------
# Action buttons (not inside a form to allow immediate effect)
# ---------------------------
st.markdown("---")
st.subheader("Acciones")
col_save, col_clear, col_search = st.columns([1,1,1])

# Helper: build row dict from current session/form
def build_row_from_inputs(input_usuario_value):
    """Crea un diccionario con todos los campos para insertar/actualizar."""
    try:
        fi = fecha_inicio if isinstance(fecha_inicio, date) else date.fromisoformat(str(fecha_inicio))
        ff = fecha_fin if isinstance(fecha_fin, date) else date.fromisoformat(str(fecha_fin))
    except Exception:
        fi = fecha_inicio
        ff = fecha_fin

    total_benef = int(beneficiarios_hombres) + int(beneficiarios_mujeres) + int(beneficiarios_glbti)
    row = {
        "created_at": datetime.utcnow().isoformat(),
        "usuario": input_usuario_value,
        "usuario_password": hash_password(st.session_state.get(P + "sidebar_password")) if st.session_state.get(P + "sidebar_password") else None,
        "nombre_proyecto": nombre_proyecto,
        "pais_intervencion": pais_intervencion,
        "provincia_departamento": provincia_departamento,
        "canton_distrito": canton_distrito,
        "pueblo_nacionalidad": pueblo_nacionalidad,
        "latitud": float(latitud or 0.0),
        "longitud": float(longitud or 0.0),
        "beneficiarios_hombres": int(beneficiarios_hombres or 0),
        "beneficiarios_mujeres": int(beneficiarios_mujeres or 0),
        "beneficiarios_glbti": int(beneficiarios_glbti or 0),
        "total_beneficiarios": total_benef,
        "fecha_inicio": fi.isoformat() if isinstance(fi, date) else str(fi),
        "fecha_fin": ff.isoformat() if isinstance(ff, date) else str(ff),
        "duracion_dias": (ff - fi).days if isinstance(fi, date) and isinstance(ff, date) else None,
        "monto_total": float(monto_total or 0.0),
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
        "meta_pb": float(meta_pb or 0.0),
        "indicador_pei": indicador_pei,
        "unidad_medida_pei": unidad_medida_pei,
        "meta_pei": float(meta_pei or 0.0),
        "indicador_proyecto": indicador_proyecto,
        "unidad_medida_proyecto": unidad_medida_proyecto,
        "meta_proyecto": float(meta_proyecto or 0.0),
        "tendencia_indicador": tendencia_indicador,
        "anio_cumplimiento_meta": int(anio_cumplimiento_meta or date.today().year),
        "anio_linea_base": int(anio_linea_base or date.today().year),
        "valor_linea_base": float(valor_linea_base or 0.0),
        "total_meta_cumplida_acumulada": float(total_meta_cumplida_acumulada or 0.0),
        "porc_ejecucion_fisica": percent(total_meta_cumplida_acumulada, meta_proyecto),
        "presupuesto_programado_total": float(presupuesto_programado_total or 0.0),
        "presupuesto_devengado_total": float(presupuesto_devengado_total or 0.0),
        "porc_ejecucion_presupuestaria": percent(presupuesto_devengado_total, presupuesto_programado_total),
        "nudos_criticos": nudos_criticos,
        "logros_relevantes": logros_relevantes,
        "aprendizajes": aprendizajes,
        "medios_de_verificacion": medios_de_verificacion,
        "nombre_responsable": nombre_responsable,
        "cargo_responsable": cargo_responsable,
        "correo_responsable": correo_responsable,
        "telefono_responsable": telefono_responsable
    }
    # yearly metas & trimestrales from session_state
    for y in years:
        row[f"meta_{y}"] = float(st.session_state.get(P + f"meta_{y}", 0.0) or 0.0)
    for t in range(1,5):
        row[f"meta_plan_{t}"] = float(st.session_state.get(P + f"meta_plan_{t}", 0.0) or 0.0)
        row[f"meta_cum_{t}"] = float(st.session_state.get(P + f"meta_cum_{t}", 0.0) or 0.0)
        row[f"pres_prog_{t}"] = float(st.session_state.get(P + f"pres_prog_{t}", 0.0) or 0.0)
        row[f"pres_dev_{t}"] = float(st.session_state.get(P + f"pres_dev_{t}", 0.0) or 0.0)
    row["meta_plan_anual"] = sum(float(st.session_state.get(P + f"meta_plan_{t}", 0.0) or 0.0) for t in range(1,5))
    row["meta_cum_anual"] = sum(float(st.session_state.get(P + f"meta_cum_{t}", 0.0) or 0.0) for t in range(1,5))
    row["pres_prog_anual"] = sum(float(st.session_state.get(P + f"pres_prog_{t}", 0.0) or 0.0) for t in range(1,5))
    row["pres_dev_anual"] = sum(float(st.session_state.get(P + f"pres_dev_{t}", 0.0) or 0.0) for t in range(1,5))
    return row

# SAVE (nuevo)
with col_save:
    if st.button("💾 Guardar (nuevo)"):
        errs = []
        input_usuario = st.session_state.get(P + "sidebar_usuario", "")
        if not input_usuario:
            errs.append("Debe iniciar sesión con un usuario antes de guardar.")
        if correo_responsable and not is_valid_email(correo_responsable):
            errs.append("Correo del responsable inválido.")
        try:
            fi = fecha_inicio if isinstance(fecha_inicio, date) else date.fromisoformat(str(fecha_inicio))
            ff = fecha_fin if isinstance(fecha_fin, date) else date.fromisoformat(str(fecha_fin))
            if ff < fi:
                errs.append("La fecha de finalización debe ser igual o posterior a la fecha de inicio.")
        except Exception:
            errs.append("Fechas inválidas.")
        if not nombre_proyecto or str(nombre_proyecto).strip() == "":
            errs.append("Nombre del proyecto es obligatorio.")
        if errs:
            for e in errs:
                st.error(e)
        else:
            try:
                row = build_row_from_inputs(input_usuario)
                cols = ','.join(row.keys())
                placeholders = ','.join('%s' for _ in row)
                cur.execute(f"INSERT INTO projects ({cols}) VALUES ({placeholders})", tuple(row.values()))
                conn.commit()
                st.success("✅ Proyecto guardado correctamente.")
                st.session_state[P + "__do_reset__"] = True
                safe_rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
                st.error(traceback.format_exc())

# --- Definir la función de limpieza ANTES del botón ---
def limpiar_todo():
    for k in SHORT_KEYS:
        st.session_state[P + k] = DEFAULTS[k]
    st.session_state[P + "sidebar_usuario"] = ""
    st.session_state[P + "__do_reset__"] = False
    # Forzar recarga segura
    safe_rerun()

# --- Crear el botón en la columna ---
with col_clear:
    st.button(
        "🧹 Limpiar formulario (incluye usuario activo)",
        on_click=limpiar_todo
    )

with col_search:
    # search by ID input
    search_id_val = st.number_input("ID a buscar / seleccionar", min_value=0, value=int(st.session_state.get(P + "search_id") or 0), step=1, key=P + "search_id")
    if st.button("🔎 Buscar / Seleccionar registro"):
        if search_id_val <= 0:
            st.error("Ingrese un ID válido mayor a 0 para buscar.")
        else:
            cur.execute("SELECT * FROM projects WHERE id = %s", (search_id_val,))
            rec = cur.fetchone()
            if not rec:
                st.error("Registro no encontrado.")
            else:
                cols = [d[0] for d in cur.description]
                recd = dict(zip(cols, rec))
                payload = {}
                # short fields to load
                load_fields = [k for k in SHORT_KEYS if k not in ("sidebar_usuario","sidebar_password","__pending_load__","__do_reset__","pending_delete_id","edit_id","search_id","filter_pueblo","filter_pais","filter_usuario")]
                for fld in load_fields:
                    if fld in recd:
                        val = recd.get(fld)
                        # convert dates to date objects if needed
                        if fld in ("fecha_inicio","fecha_fin") and val:
                            try:
                                val = date.fromisoformat(val)
                            except Exception:
                                try:
                                    val = datetime.fromisoformat(val).date()
                                except Exception:
                                    val = DEFAULTS[fld]
                        payload[fld] = val if (val is not None) else DEFAULTS[fld]
                # yearly metas & trimestrales may be in recd
                for y in years:
                    payload[f"meta_{y}"] = recd.get(f"meta_{y}", DEFAULTS.get(f"meta_{y}", 0.0))
                for t in range(1,5):
                    payload[f"meta_plan_{t}"] = recd.get(f"meta_plan_{t}", DEFAULTS.get(f"meta_plan_{t}", 0.0))
                    payload[f"meta_cum_{t}"] = recd.get(f"meta_cum_{t}", DEFAULTS.get(f"meta_cum_{t}", 0.0))
                    payload[f"pres_prog_{t}"] = recd.get(f"pres_prog_{t}", DEFAULTS.get(f"pres_prog_{t}", 0.0))
                    payload[f"pres_dev_{t}"] = recd.get(f"pres_dev_{t}", DEFAULTS.get(f"pres_dev_{t}", 0.0))
                # años
                payload["anio_cumplimiento_meta"] = max(int(recd.get("anio_cumplimiento_meta") or date.today().year), 1900)
                payload["anio_linea_base"] = max(int(recd.get("anio_linea_base") or date.today().year), 1900)
                # mark edit id
                payload["_edit_id_"] = search_id_val
                st.session_state[P + "__pending_load__"] = payload
                # also store current usuario_password from record (if any) in session_state to preserve on update if user doesn't change password
                st.session_state[P + "usuario_password"] = recd.get("usuario_password")
                # set edit id explicitly
                st.session_state[P + "edit_id"] = search_id_val
                safe_rerun()

# ---------------------------
# Update / Delete / Export
# ---------------------------
st.markdown("---")
col_upd, col_del, col_export = st.columns([1,1,1])

with col_upd:
    if st.button("🔁 Actualizar registro seleccionado"):
        edit_id = st.session_state.get(P + "edit_id")
        if not edit_id:
            st.error("No hay registro seleccionado. Use Buscar para cargar uno antes de actualizar.")
        else:
            errs = []
            input_usuario = st.session_state.get(P + "sidebar_usuario", "")
            if not input_usuario or str(input_usuario).strip() == "":
                errs.append("Debe iniciar sesión con un usuario antes de actualizar.")
            if st.session_state[P + "correo_responsable"] and not is_valid_email(st.session_state[P + "correo_responsable"]):
                errs.append("Correo del responsable inválido.")
            try:
                fi = st.session_state[P + "fecha_inicio"]
                ff = st.session_state[P + "fecha_fin"]
                if not isinstance(fi, date) or not isinstance(ff, date):
                    errs.append("Fechas inválidas.")
                elif ff < fi:
                    errs.append("La fecha de finalización debe ser igual o posterior a la fecha de inicio.")
            except Exception:
                errs.append("Fechas inválidas.")
            if not st.session_state[P + "nombre_proyecto"] or str(st.session_state[P + "nombre_proyecto"]).strip() == "":
                errs.append("Nombre del proyecto es obligatorio.")
            if errs:
                for e in errs:
                    st.error(e)
            else:
                try:
                    # permission: only creator or admin can update
                    cur.execute("SELECT usuario FROM projects WHERE id=%s", (edit_id,))
                    rec = cur.fetchone()
                    owner = rec[0] if rec else None
                    if (not is_admin) and (owner != input_usuario):
                        st.error("No tienes permiso para actualizar (solo el creador o admin).")
                    else:
                        # build row from session fields (preserve usuario_password if empty)
                        row = {
                            "usuario": input_usuario,
                            "usuario_password": hash_password(st.session_state.get(P + "sidebar_password")) if st.session_state.get(P + "sidebar_password") else st.session_state.get(P + "usuario_password"),
                            "nombre_proyecto": st.session_state[P + "nombre_proyecto"],
                            "pais_intervencion": st.session_state[P + "pais_intervencion"],
                            "provincia_departamento": st.session_state[P + "provincia_departamento"],
                            "canton_distrito": st.session_state[P + "canton_distrito"],
                            "pueblo_nacionalidad": st.session_state[P + "pueblo_nacionalidad"],
                            "latitud": float(st.session_state[P + "latitud"] or 0.0),
                            "longitud": float(st.session_state[P + "longitud"] or 0.0),
                            "beneficiarios_hombres": int(st.session_state[P + "beneficiarios_hombres"] or 0),
                            "beneficiarios_mujeres": int(st.session_state[P + "beneficiarios_mujeres"] or 0),
                            "beneficiarios_glbti": int(st.session_state[P + "beneficiarios_glbti"] or 0),
                            "total_beneficiarios": int(st.session_state[P + "beneficiarios_hombres"]) + int(st.session_state[P + "beneficiarios_mujeres"]) + int(st.session_state[P + "beneficiarios_glbti"]),
                            "fecha_inicio": st.session_state[P + "fecha_inicio"].isoformat() if isinstance(st.session_state[P + "fecha_inicio"], date) else str(st.session_state[P + "fecha_inicio"]),
                            "fecha_fin": st.session_state[P + "fecha_fin"].isoformat() if isinstance(st.session_state[P + "fecha_fin"], date) else str(st.session_state[P + "fecha_fin"]),
                            "duracion_dias": (st.session_state[P + "fecha_fin"] - st.session_state[P + "fecha_inicio"]).days if isinstance(st.session_state[P + "fecha_inicio"], date) and isinstance(st.session_state[P + "fecha_fin"], date) else None,
                            "monto_total": float(st.session_state[P + "monto_total"] or 0.0),
                            "fuente_financiamiento": st.session_state[P + "fuente_financiamiento"],
                            "entidad_ejecutora": st.session_state[P + "entidad_ejecutora"],
                            "eje_plan_biorregional": st.session_state[P + "eje_plan_biorregional"],
                            "eje_tematico_plan_biorregional": st.session_state[P + "eje_tematico_plan_biorregional"],
                            "estrategia_plan_biorregional": st.session_state[P + "estrategia_plan_biorregional"],
                            "accion_plan_biorregional": st.session_state[P + "accion_plan_biorregional"],
                            "objetivo_estrategico_pei": st.session_state[P + "objetivo_estrategico_pei"],
                            "estrategia_pei": st.session_state[P + "estrategia_pei"],
                            "indicador_pb": st.session_state[P + "indicador_pb"],
                            "unidad_medida_pb": st.session_state[P + "unidad_medida_pb"],
                            "meta_pb": float(st.session_state[P + "meta_pb"] or 0.0),
                            "indicador_pei": st.session_state[P + "indicador_pei"],
                            "unidad_medida_pei": st.session_state[P + "unidad_medida_pei"],
                            "meta_pei": float(st.session_state[P + "meta_pei"] or 0.0),
                            "indicador_proyecto": st.session_state[P + "indicador_proyecto"],
                            "unidad_medida_proyecto": st.session_state[P + "unidad_medida_proyecto"],
                            "meta_proyecto": float(st.session_state[P + "meta_proyecto"] or 0.0),
                            "tendencia_indicador": st.session_state[P + "tendencia_indicador"],
                            "anio_cumplimiento_meta": int(st.session_state[P + "anio_cumplimiento_meta"] or date.today().year),
                            "anio_linea_base": int(st.session_state[P + "anio_linea_base"] or date.today().year),
                            "valor_linea_base": float(st.session_state[P + "valor_linea_base"] or 0.0),
                            "total_meta_cumplida_acumulada": float(st.session_state[P + "total_meta_cumplida_acumulada"] or 0.0),
                            "porc_ejecucion_fisica": percent(st.session_state[P + "total_meta_cumplida_acumulada"], st.session_state[P + "meta_proyecto"]),
                            "presupuesto_programado_total": float(st.session_state[P + "presupuesto_programado_total"] or 0.0),
                            "presupuesto_devengado_total": float(st.session_state[P + "presupuesto_devengado_total"] or 0.0),
                            "porc_ejecucion_presupuestaria": percent(st.session_state[P + "presupuesto_devengado_total"], st.session_state[P + "presupuesto_programado_total"]),
                            "nudos_criticos": st.session_state[P + "nudos_criticos"],
                            "logros_relevantes": st.session_state[P + "logros_relevantes"],
                            "aprendizajes": st.session_state[P + "aprendizajes"],
                            "medios_de_verificacion": st.session_state[P + "medios_de_verificacion"],
                            "nombre_responsable": st.session_state[P + "nombre_responsable"],
                            "cargo_responsable": st.session_state[P + "cargo_responsable"],
                            "correo_responsable": st.session_state[P + "correo_responsable"],
                            "telefono_responsable": st.session_state[P + "telefono_responsable"],
                        }
                        for y in years:
                            row[f"meta_{y}"] = float(st.session_state.get(P + f"meta_{y}", 0.0) or 0.0)
                        for t in range(1,5):
                            row[f"meta_plan_{t}"] = float(st.session_state.get(P + f"meta_plan_{t}", 0.0) or 0.0)
                            row[f"meta_cum_{t}"] = float(st.session_state.get(P + f"meta_cum_{t}", 0.0) or 0.0)
                            row[f"pres_prog_{t}"] = float(st.session_state.get(P + f"pres_prog_{t}", 0.0) or 0.0)
                            row[f"pres_dev_{t}"] = float(st.session_state.get(P + f"pres_dev_{t}", 0.0) or 0.0)
                        assignments = ','.join([f"{k}=%s" for k in row.keys()])
                        values = tuple(row.values()) + (edit_id,)
                        cur.execute(f"UPDATE projects SET {assignments} WHERE id=%s", values)
                        conn.commit()
                        st.success(f"✅ Registro ID {edit_id} actualizado correctamente.")
                        st.session_state[P + "__do_reset__"] = True
                        safe_rerun()
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")
                    st.error(traceback.format_exc())

with col_del:
    if st.button("🗑️ Marcar registro para eliminación"):
        edit_id = st.session_state.get(P + "edit_id")
        if not edit_id:
            st.error("No hay registro seleccionado. Use Buscar para cargar el registro antes de eliminar.")
        else:
            st.session_state[P + "pending_delete_id"] = edit_id
            st.success(f"Registro ID {edit_id} marcado para eliminación. Confirma abajo.")
            safe_rerun()

    if st.session_state.get(P + "pending_delete_id"):
        st.markdown("**Confirmar eliminación**")
        pdid = st.session_state[P + "pending_delete_id"]
        cur.execute("SELECT id, nombre_proyecto, usuario FROM projects WHERE id=%s", (pdid,))
        rec = cur.fetchone()
        if rec:
            st.write(f"ID: {rec[0]} — Proyecto: **{rec[1]}** — Usuario creador: **{rec[2]}**")
        else:
            st.warning("El registro ya no existe.")
        col_confirm, col_cancel = st.columns([1,1])
        with col_confirm:
            if st.button("CONFIRMAR ELIMINACIÓN"):
                try:
                    if not rec:
                        st.error("Registro no encontrado.")
                    else:
                        owner = rec[2]
                        input_usuario = st.session_state.get(P + "sidebar_usuario", "")
                        if (not is_admin) and (owner != input_usuario):
                            st.error("No tienes permiso para eliminar (solo el creador o admin).")
                        else:
                            cur.execute("DELETE FROM projects WHERE id=%s", (pdid,))
                            conn.commit()
                            st.success(f"Registro ID {pdid} eliminado correctamente.")
                            st.session_state[P + "__do_reset__"] = True
                            st.session_state[P + "pending_delete_id"] = None
                            safe_rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {e}")
                    st.error(traceback.format_exc())
        with col_cancel:
            if st.button("CANCELAR ELIMINACIÓN"):
                st.session_state[P + "pending_delete_id"] = None
                st.info("Eliminación cancelada.")
                safe_rerun()

with col_export:
    if st.button("⬇️ Exportar (Excel / CSV)"):
        try:
            df_all = pd.read_sql_query("SELECT * FROM projects ORDER BY created_at DESC", conn)
            if df_all.empty:
                st.info("No hay registros para exportar.")
            else:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_all.to_excel(writer, index=False, sheet_name="projects")
                buf.seek(0)
                st.download_button("Descargar Excel", data=buf.getvalue(), file_name=f"simsea_projects_{datetime.utcnow().date()}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # CSV
                csv_buf = df_all.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar CSV", data=csv_buf, file_name=f"simsea_projects_{datetime.utcnow().date()}.csv",
                                   mime="text/csv")
        except Exception as e:
            st.error(f"Error al exportar: {e}")
            st.error(traceback.format_exc())

# ---------------------------
# Panel / list & filters
# ---------------------------
st.markdown("---")
st.header("Panel: consulta y administración de registros")
try:
    df = pd.read_sql_query("SELECT * FROM projects ORDER BY created_at DESC", conn)
except Exception:
    df = pd.DataFrame()

st.subheader(f"Registros: {len(df)}")

with st.expander("Filtros"):
    filtro_pueblo = st.text_input("Filtrar por pueblo / nacionalidad", value=st.session_state.get(P + "filter_pueblo",""))
    filtro_pais = st.selectbox("Filtrar por país", ["", "Ecuador","Perú","Biorregional: Ecuador – Perú"], index=0)
    filtro_usuario = st.text_input("Filtrar por usuario", value=st.session_state.get(P + "filter_usuario",""))
    if filtro_pueblo and 'pueblo_nacionalidad' in df.columns:
        df = df[df['pueblo_nacionalidad'].astype(str).str.contains(filtro_pueblo, case=False, na=False)]
    if filtro_pais and filtro_pais != "" and 'pais_intervencion' in df.columns:
        df = df[df['pais_intervencion'] == filtro_pais]
    if filtro_usuario and 'usuario' in df.columns:
        df = df[df['usuario'].astype(str).str.contains(filtro_usuario, case=False, na=False)]

if df.empty:
    st.info("No hay registros para mostrar.")
else:
    # show key columns and allow selecting a row to load (conveniencia)
    st.dataframe(df, use_container_width=True)
    st.markdown("**Seleccionar registro para edición**")
    try:
        selectable = df[["id","nombre_proyecto","usuario","pais_intervencion"]].copy()
        selectable["label"] = selectable.apply(lambda r: f"ID {r['id']} — {r['nombre_proyecto']} — {r['usuario']} — {r['pais_intervencion']}", axis=1)
        choice = st.selectbox("Seleccionar registro por lista", options=[""] + selectable["label"].tolist(), index=0)
        if choice:
            sel_id = int(choice.split()[1])
            st.session_state[P + "search_id"] = sel_id
            # trigger a fetch similar to Buscar
            cur.execute("SELECT * FROM projects WHERE id = %s", (sel_id,))
            rec = cur.fetchone()
            if rec:
                cols = [d[0] for d in cur.description]
                recd = dict(zip(cols, rec))
                payload = {}
                load_fields = [k for k in SHORT_KEYS if k not in ("sidebar_usuario","sidebar_password","__pending_load__","__do_reset__","pending_delete_id","edit_id","search_id","filter_pueblo","filter_pais","filter_usuario")]
                for fld in load_fields:
                    if fld in recd:
                        val = recd.get(fld)
                        if fld in ("fecha_inicio","fecha_fin") and val:
                            try:
                                val = date.fromisoformat(val)
                            except Exception:
                                try:
                                    val = datetime.fromisoformat(val).date()
                                except Exception:
                                    val = DEFAULTS[fld]
                        payload[fld] = val if (val is not None) else DEFAULTS[fld]
                for y in years:
                    payload[f"meta_{y}"] = recd.get(f"meta_{y}", DEFAULTS.get(f"meta_{y}", 0.0))
                for t in range(1,5):
                    payload[f"meta_plan_{t}"] = recd.get(f"meta_plan_{t}", DEFAULTS.get(f"meta_plan_{t}", 0.0))
                    payload[f"meta_cum_{t}"] = recd.get(f"meta_cum_{t}", DEFAULTS.get(f"meta_cum_{t}", 0.0))
                    payload[f"pres_prog_{t}"] = recd.get(f"pres_prog_{t}", DEFAULTS.get(f"pres_prog_{t}", 0.0))
                    payload[f"pres_dev_{t}"] = recd.get(f"pres_dev_{t}", DEFAULTS.get(f"pres_dev_{t}", 0.0))
                payload["anio_cumplimiento_meta"] = max(int(recd.get("anio_cumplimiento_meta") or date.today().year), 1900)
                payload["anio_linea_base"] = max(int(recd.get("anio_linea_base") or date.today().year), 1900)
                payload["_edit_id_"] = sel_id
                st.session_state[P + "__pending_load__"] = payload
                st.session_state[P + "usuario_password"] = recd.get("usuario_password")
                safe_rerun()
    except Exception:
        # no blocking error for panel
        pass

st.markdown("---")
st.caption("Consejo: configure SIMSEA_ADMIN_USER y SIMSEA_ADMIN_PASSWORD como variables de entorno en producción y haga backups regulares de SIMSEA.db")











