import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from economic_tools import FUNCIONES_DISPONIBLES

load_dotenv()

st.set_page_config(page_title="Agente Económico IA", page_icon="💹", layout="wide")

from supabase import create_client


def leer_secreto(nombre):
    try:
        return st.secrets[nombre]
    except Exception:
        return os.getenv(nombre)


API_KEY = leer_secreto("GROQ_API_KEY")
if not API_KEY:
    st.error("No se encontró GROQ_API_KEY.")
    st.stop()

client = Groq(api_key=API_KEY)


@st.cache_resource
def conectar_supabase():
    url, key = leer_secreto("SUPABASE_URL"), leer_secreto("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


db = conectar_supabase()


def registrar_consulta(pregunta, herramientas):
    if db is None:
        return
    try:
        db.table("consultas").insert({
            "pregunta": pregunta[:500],
            "herramientas": ", ".join(herramientas)}).execute()
    except Exception:
        pass


def total_consultas():
    if db is None:
        return st.session_state.consultas
    try:
        r = db.table("consultas").select("id", count="exact").limit(1).execute()
        return r.count or 0
    except Exception:
        return st.session_state.consultas
MODELO = "openai/gpt-oss-120b"
MAX_ITERACIONES = 6
LIMITE_MEMORIA = 20

SYSTEM_PROMPT = """Eres un AGENTE ECONOMICO especializado en analisis financiero
y macroeconomico, con enfoque en Guatemala y Centroamerica.

OBJETIVO:
Entregar informacion economica verificada y su interpretacion, para apoyar
decisiones de conversion de divisas, inversion y analisis de contexto
macroeconomico. Nunca inventas cifras: toda cifra que reportes debe provenir
de una herramienta ejecutada en esta misma conversacion.

REGLAS DE OPERACION:
1. Si la pregunta requiere un dato numerico actual, DEBES llamar a la
   herramienta correspondiente antes de responder.
2. Puedes encadenar varias herramientas en una misma respuesta.
3. Cita siempre la fuente y la fecha del dato.
4. Despues del dato, agrega una interpretacion economica breve.
5. Usa quetzales (GTQ) como referencia si el usuario no especifica otra moneda.
6. Si una herramienta falla, informalo. No rellenes el vacio con estimaciones.
7. Responde en espanol, conciso y profesional.

ALCANCE:
No das recomendaciones personalizadas de inversion. Presentas datos y analisis.
"""

RUTA_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "economic_tools.json")
with open(RUTA_JSON, "r", encoding="utf-8") as f:
    TOOLS = json.load(f)

if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
if "historial_visible" not in st.session_state:
    st.session_state.historial_visible = []
if "consultas" not in st.session_state:
    st.session_state.consultas = 0


def recortar_memoria():
    if len(st.session_state.mensajes) > LIMITE_MEMORIA + 1:
        st.session_state.mensajes = [st.session_state.mensajes[0]] + st.session_state.mensajes[-LIMITE_MEMORIA:]


def ejecutar_herramienta(nombre, argumentos):
    funcion = FUNCIONES_DISPONIBLES.get(nombre)
    if funcion is None:
        return {"error": f"La herramienta '{nombre}' no existe."}
    try:
        return funcion(**argumentos)
    except Exception as e:
        return {"error": f"Fallo la ejecucion de '{nombre}': {e}"}


def construir_grafica(resultados):
    for nombre, resultado in resultados:
        if not isinstance(resultado, dict) or "error" in resultado:
            continue
        if nombre == "historico_tipo_cambio" and "serie" in resultado:
            df = pd.DataFrame(resultado["serie"]).set_index("fecha")
            return {"tipo": "linea", "titulo": f"Histórico {resultado.get('par', '')}", "df": df}
        if nombre == "indicador_macro" and "serie_reciente" in resultado:
            df = pd.DataFrame(resultado["serie_reciente"]).set_index("anio")
            titulo = f"{resultado.get('indicador', '').capitalize()} — {resultado.get('pais', '')}"
            return {"tipo": "linea", "titulo": titulo, "df": df}
        if nombre == "comparar_monedas" and "tasas" in resultado:
            tasas = {k: v for k, v in resultado["tasas"].items() if isinstance(v, (int, float))}
            if tasas:
                df = pd.DataFrame({"tasa": tasas})
                titulo = f"{resultado.get('moneda_base', '')} frente a otras monedas"
                return {"tipo": "barra", "titulo": titulo, "df": df}
    return None


def responder(mensaje_usuario):
    st.session_state.mensajes.append({"role": "user", "content": mensaje_usuario})
    resultados_turno = []

    for _ in range(MAX_ITERACIONES):
        respuesta = client.chat.completions.create(
            model=MODELO, messages=st.session_state.mensajes, tools=TOOLS,
            tool_choice="auto", temperature=0.3)
        mensaje = respuesta.choices[0].message
        llamadas = mensaje.tool_calls

        if not llamadas:
            st.session_state.mensajes.append({"role": "assistant", "content": mensaje.content})
            recortar_memoria()
            return mensaje.content, resultados_turno

        st.session_state.mensajes.append({
            "role": "assistant", "content": mensaje.content,
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments}}
                           for c in llamadas]})

        for llamada in llamadas:
            nombre = llamada.function.name
            try:
                argumentos = json.loads(llamada.function.arguments or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            resultado = ejecutar_herramienta(nombre, argumentos)
            resultados_turno.append((nombre, resultado))
            st.session_state.mensajes.append({"role": "tool", "tool_call_id": llamada.id,
                                              "name": nombre,
                                              "content": json.dumps(resultado, ensure_ascii=False)})

    return "Se alcanzó el límite de pasos sin llegar a una respuesta final.", resultados_turno


with st.sidebar:
    st.markdown("## 💹 Agente Económico IA")
    st.caption("Tu asistente económico de confianza")
    st.divider()
    st.markdown("### ¿Qué puedo hacer?")
    st.write("Consulto tipos de cambio, criptomonedas e indicadores macroeconómicos "
             "en tiempo real desde fuentes oficiales, y explico lo que significan.")
    st.divider()
    st.markdown("### 🔧 Herramientas conectadas")
    for h in TOOLS:
        st.markdown(f"- `{h['function']['name']}`")
    st.divider()
    st.markdown("### 📊 Consultas realizadas")
    st.markdown(f"<h2 style='text-align:center'>{total_consultas()}</h2>", unsafe_allow_html=True)

st.title("💹 Agente Económico IA")
st.caption("Práctica 1 · Data Analytics · Universidad Rafael Landívar")

for turno in st.session_state.historial_visible:
    with st.chat_message(turno["role"]):
        st.markdown(turno["content"])
        if turno.get("grafica"):
            g = turno["grafica"]
            st.markdown(f"**{g['titulo']}**")
            if g["tipo"] == "linea":
                st.line_chart(g["df"])
            else:
                st.bar_chart(g["df"])

LIMITE_SESION = 15

entrada = st.chat_input("Escribe tu pregunta o solicitud...")
if entrada:
    if st.session_state.consultas >= LIMITE_SESION:
        st.warning(f"Alcanzaste el límite de {LIMITE_SESION} consultas por sesión.")
        st.stop()

    st.session_state.historial_visible.append({"role": "user", "content": entrada})
    with st.chat_message("user"):
        st.markdown(entrada)

    with st.chat_message("assistant"):
        with st.spinner("Consultando fuentes económicas..."):
            texto, resultados = responder(entrada)
        st.markdown(texto)
        grafica = construir_grafica(resultados)
        if grafica:
            st.markdown(f"**{grafica['titulo']}**")
            if grafica["tipo"] == "linea":
                st.line_chart(grafica["df"])
            else:
                st.bar_chart(grafica["df"])

    registrar_consulta(entrada, [n for n, _ in resultados])
    st.session_state.consultas += 1
    st.session_state.historial_visible.append({"role": "assistant", "content": texto, "grafica": grafica})
    st.rerun()