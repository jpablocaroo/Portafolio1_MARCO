"""
App básica de Streamlit — Nivel de ríos/quebradas (CORNARE / MARCO)
--------------------------------------------------------------------
Versión con parámetros fijos (no editables), consulta automática al
cargar la página, y sección final para subir una foto de evidencia.

Para correrla:
    streamlit run app_nivel_cornare.py
"""

import requests
import pandas as pd
import numpy as np
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------------------------
# Coordenadas por defecto (Institución Universitaria Pascual Bravo)
# Se usan solo si la API no trae la latitud/longitud de la estación.
# ------------------------------------------------------------------
LAT_DEFECTO = 6.1703
LON_DEFECTO = -75.4359

API_BASE_URL = "https://marco.cornare.gov.co/api/v1/estaciones"

LLAVE_FECHA = "level_date"
LLAVE_VALOR = "level"
CANDIDATOS_LAT = ["lat", "latitude", "latitud"]
CANDIDATOS_LON = ["lng", "lon", "longitude", "longitud"]

st.set_page_config(page_title="Nivel de estación — CORNARE", page_icon="🌊", layout="wide")

# ------------------------------------------------------------------
# Parámetros FIJOS de la consulta (edítalos aquí en el código, no
# desde la interfaz). Cada estudiante debe cambiar estos valores
# antes de correr la app.
# ------------------------------------------------------------------
NOMBRE_ESTUDIANTE = "Juan Pablo Caro Osorio"
CODIGO_ESTACION = "6"
FECHA_DESDE = pd.to_datetime("2026-08-28").strftime("%Y-%m-%d")
FECHA_HASTA = pd.to_datetime("2026-09-01").strftime("%Y-%m-%d")
CALIDAD = 1  # 1 = solo datos validados

NOMBRE_ESTACION = "Quebrada Yarumal"
UBICACION_ESTACION = "Rionegro Cod.6"
RUTA_FOTO_ESTACION = "PortafolioMARCO.jpg"

# ------------------------------------------------------------------
# Funciones de consulta
# ------------------------------------------------------------------
def obtener_serie_nivel(codigo_estacion, desde, hasta, calidad=1, timeout=30):
    url = f"{API_BASE_URL}/{codigo_estacion}/nivel"
    params = {"desde": desde, "hasta": hasta, "calidad": calidad}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout, verify=False)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"HTTP {resp.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


def obtener_todas_las_paginas(datos_json, timeout=30):
    registros = list(datos_json.get("values", []))
    siguiente_url = datos_json.get("next")
    while siguiente_url:
        try:
            resp = requests.get(siguiente_url, timeout=timeout, verify=False)
        except requests.exceptions.RequestException:
            break
        if resp.status_code != 200:
            break
        pagina = resp.json()
        registros.extend(pagina.get("values", []))
        siguiente_url = pagina.get("next")
    return registros


def detectar_coordenadas(datos_json):
    """Busca lat/lon en las llaves raíz de la respuesta. Si no las encuentra, usa el valor por defecto."""
    if not isinstance(datos_json, dict):
        return LAT_DEFECTO, LON_DEFECTO, False

    lat = next((datos_json[k] for k in CANDIDATOS_LAT if k in datos_json), None)
    lon = next((datos_json[k] for k in CANDIDATOS_LON if k in datos_json), None)

    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon), True
        except (TypeError, ValueError):
            pass
    return LAT_DEFECTO, LON_DEFECTO, False


def calcular_indice_calidad(df):
    """Índice simple (0-100) combinando completitud de la serie y proporción de outliers."""
    if df.empty or len(df) < 2:
        return 0.0, 0, 0

    df_idx = df.set_index("fecha")
    frecuencia_tipica = df["fecha"].diff().dropna().mode()
    if len(frecuencia_tipica) == 0:
        return 0.0, 0, 0
    frecuencia_tipica = frecuencia_tipica[0]

    rango_completo = pd.date_range(start=df_idx.index.min(), end=df_idx.index.max(), freq=frecuencia_tipica)
    esperados = len(rango_completo)
    huecos = esperados - len(df_idx)
    completitud = max(0.0, 1 - (huecos / esperados)) if esperados > 0 else 0.0

    Q1, Q3 = df["nivel"].quantile(0.25), df["nivel"].quantile(0.75)
    IQR = Q3 - Q1
    lim_inf, lim_sup = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    es_outlier = (df["nivel"] < lim_inf) | (df["nivel"] > lim_sup) | (df["nivel"] < 0)
    proporcion_outliers = es_outlier.mean()

    indice = (completitud * 0.7 + (1 - proporcion_outliers) * 0.3) * 100
    return round(indice, 1), int(huecos), int(es_outlier.sum())

st.sidebar.header("Parámetros de la consulta")
st.sidebar.markdown(f"**Nombre del estudiante:** {NOMBRE_ESTUDIANTE}")
st.sidebar.markdown(f"**Código de estación:** {CODIGO_ESTACION}")
st.sidebar.markdown(f"**Desde:** {FECHA_DESDE}")
st.sidebar.markdown(f"**Hasta:** {FECHA_HASTA}")
st.sidebar.markdown(f"**Calidad:** {'1 = datos validados' if CALIDAD == 1 else '0 = todos los datos'}")

st.title("🌊 Nivel de ríos y quebradas — CORNARE")
st.caption(f"Estudiante: **{NOMBRE_ESTUDIANTE}** · Estación: **{CODIGO_ESTACION}**")

st.divider()
col_foto, col_info = st.columns([1, 2])
with col_foto:
    try:
        st.image(RUTA_FOTO_ESTACION, use_container_width=True)
    except Exception:
        st.info("Coloca la foto en `RUTA_FOTO_ESTACION` para que aparezca aquí.")
with col_info:
    st.markdown(f"### {NOMBRE_ESTACION}")
    st.markdown(f"📍 **Ubicación:** {UBICACION_ESTACION}")
    st.markdown(f"🔢 **Código de estación:** {CODIGO_ESTACION}")
st.divider()

with st.spinner("Consultando la API..."):
    datos_crudos, error = obtener_serie_nivel(CODIGO_ESTACION, FECHA_DESDE, FECHA_HASTA, CALIDAD)

if error:
    st.error(f"❌ {error}")
else:
    registros = obtener_todas_las_paginas(datos_crudos)

    if not registros:
        st.warning("No hay registros para esta estación y rango de fechas. Ajusta los valores fijos en el código.")
    else:
        df = pd.DataFrame(registros)
        df = df.rename(columns={LLAVE_FECHA: "fecha", LLAVE_VALOR: "nivel"})
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")
        df = df.dropna(subset=["fecha", "nivel"]).sort_values("fecha").reset_index(drop=True)

        lat, lon, coords_reales = detectar_coordenadas(datos_crudos)
        indice_calidad, huecos, n_outliers = calcular_indice_calidad(df)

        # --- Métricas principales ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Lecturas", len(df))
        col2.metric("Nivel promedio", f"{df['nivel'].mean():.2f}")
        col3.metric("Índice de calidad", f"{indice_calidad} / 100")
        col4.metric("Outliers detectados", n_outliers)

        # --- Gráfico de la serie ---
        st.subheader("Serie de nivel")
        st.line_chart(df.set_index("fecha")["nivel"])

        # --- Mapa de la estación ---
        st.subheader("Ubicación de la estación")
        if not coords_reales:
            st.caption("La API no trajo latitud/longitud de la estación — se muestra el punto de partida (Pascual Bravo). Ajusta `CANDIDATOS_LAT` / `CANDIDATOS_LON` si conoces el nombre real de esas llaves.")
        st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=10)

        # --- Detalle de calidad ---
        with st.expander("Detalle del índice de calidad"):
            st.write(f"- Huecos de reporte detectados: **{huecos}**")
            st.write(f"- Outliers (IQR + nivel negativo): **{n_outliers}** de {len(df)} lecturas")
            st.write("El índice combina completitud de la serie (70%) y proporción de datos sin outliers (30%).")

        # --- Tabla y descarga ---
        with st.expander("Ver datos crudos"):
            st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar CSV", csv, file_name=f"nivel_estacion_{CODIGO_ESTACION}.csv", mime="text/csv")
