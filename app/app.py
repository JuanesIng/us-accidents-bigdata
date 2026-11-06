"""
Dashboard: Accidentes de tránsito en EE. UU. (2016–2023)
Proyecto integrador Big Data 2026-2 · Universidad Santo Tomás, Seccional Tunja
Integrantes: Diego Esteban Buitrago, Camilo Hernández y Juan Esteban Tovar

Lee solo la capa oro (data/gold), así que no necesita Spark.
Ejecutar desde la raíz del repositorio:  streamlit run app/app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"
ANIO_PARCIAL = 2023
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Paleta: gris asfalto + ámbar de señalización + rojo para gravedad
ASFALTO, AMBAR, ROJO = "#3B4147", "#E8A317", "#C0392B"
ESCALA = ["#FFF4D6", "#F5C451", AMBAR, "#D9661F", ROJO]

st.set_page_config(page_title="Accidentes de tránsito en EE. UU.", layout="wide")


@st.cache_data
def cargar(nombre: str) -> pd.DataFrame:
    return pd.read_parquet(GOLD / nombre)


def pct(graves, total):
    return 0.0 if total == 0 else 100 * graves / total


def miles(n):
    return f"{n:,.0f}".replace(",", ".")


try:
    ame = cargar("accidentes_anio_mes_estado")
    hd = cargar("accidentes_hora_dia")
except Exception:
    st.error(f"No se encontraron las tablas de la capa oro en {GOLD}. "
             "Descarga la carpeta data/gold desde Drive y ejecuta la app desde la raíz del repositorio.")
    st.stop()

# ---------- Filtros ----------
st.sidebar.header("Filtros")
anio_min, anio_max = int(ame["year"].min()), int(ame["year"].max())
rango = st.sidebar.slider("Años", anio_min, anio_max,
                          (anio_min, min(anio_max, ANIO_PARCIAL - 1)))
nombres = sorted(ame["state_name"].dropna().unique())
estados_sel = st.sidebar.multiselect("Estados", nombres, placeholder="Todos los estados")
codigos_sel = ame.loc[ame["state_name"].isin(estados_sel), "state"].unique()

def filtrar(df):
    m = df["year"].between(*rango)
    if estados_sel:
        m &= df["state"].isin(codigos_sel)
    return df[m]

f_ame, f_hd = filtrar(ame), filtrar(hd)
if rango[1] >= ANIO_PARCIAL:
    st.sidebar.caption("2023 solo tiene datos de enero a marzo.")

# ---------- Encabezado y KPI ----------
st.title("Accidentes de tránsito en EE. UU.")
st.caption("Fuente: US Accidents (2016–2023), Moosavi et al., Kaggle · Capa oro del proyecto")

if f_ame.empty:
    st.warning("No hay accidentes para estos filtros. Amplía el rango de años o quita algún estado.")
    st.stop()

total = int(f_ame["accidentes"].sum())
graves = int(f_ame["graves"].sum())
por_estado = f_ame.groupby(["state", "state_name"], as_index=False)[["accidentes", "graves"]].sum()
top = por_estado.sort_values("accidentes", ascending=False).iloc[0]
por_hora = f_hd.groupby("hour", as_index=False)["accidentes"].sum()
hora_pico = int(por_hora.sort_values("accidentes", ascending=False).iloc[0]["hour"])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Accidentes", miles(total))
k2.metric("Accidentes graves (severidad 3–4)", f"{pct(graves, total):.1f} %")
k3.metric("Estado con más accidentes", top["state_name"], f"{miles(top['accidentes'])} accidentes",
          delta_color="off")
k4.metric("Hora con más accidentes", f"{hora_pico}:00")

tab1, tab2 = st.tabs(["Evolución y estados", "Horas y días de la semana"])

# ---------- Pregunta 1 ----------
with tab1:
    st.subheader("¿Cómo evolucionaron los accidentes y dónde se concentran?")
    por_anio = f_ame.groupby("year", as_index=False)[["accidentes", "graves"]].sum()
    fig_linea = px.line(por_anio, x="year", y="accidentes", markers=True,
                        labels={"year": "Año", "accidentes": "Accidentes"},
                        color_discrete_sequence=[ASFALTO])
    fig_linea.update_xaxes(dtick=1)
    st.plotly_chart(fig_linea, width="stretch")

    c1, c2 = st.columns([3, 2])
    with c1:
        fig_mapa = px.choropleth(por_estado, locations="state", locationmode="USA-states",
                                 color="accidentes", scope="usa", hover_name="state_name",
                                 color_continuous_scale=ESCALA,
                                 labels={"accidentes": "Accidentes"})
        fig_mapa.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_mapa, width="stretch")
    with c2:
        top10 = por_estado.sort_values("accidentes", ascending=False).head(10)
        top10["pct_graves"] = (100 * top10["graves"] / top10["accidentes"]).round(1)
        fig_top = px.bar(top10.sort_values("accidentes"), x="accidentes", y="state_name",
                         orientation="h", color="pct_graves", color_continuous_scale=ESCALA,
                         labels={"accidentes": "Accidentes", "state_name": "",
                                 "pct_graves": "% graves"},
                         title="Los 10 estados con más accidentes")
        st.plotly_chart(fig_top, width="stretch")

# ---------- Pregunta 2 ----------
with tab2:
    st.subheader("¿Cuándo ocurren los accidentes y cuándo son más graves?")
    medida = st.radio("Mostrar", ["Número de accidentes", "% de accidentes graves"], horizontal=True)
    hd_agg = f_hd.groupby(["day_name", "hour"], as_index=False)[["accidentes", "graves"]].sum()
    hd_agg["valor"] = (hd_agg["accidentes"] if medida == "Número de accidentes"
                       else (100 * hd_agg["graves"] / hd_agg["accidentes"]).round(1))
    matriz = (hd_agg.pivot(index="day_name", columns="hour", values="valor")
                    .reindex(DIAS).reindex(columns=range(24)))
    fig_calor = px.imshow(matriz, aspect="auto", color_continuous_scale=ESCALA,
                          labels={"x": "Hora del día", "y": "", "color": medida})
    fig_calor.update_xaxes(dtick=1)
    st.plotly_chart(fig_calor, width="stretch")
    st.caption("Hora local del accidente. Severidad grave = niveles 3 y 4 del dataset.")
