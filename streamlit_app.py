import streamlit as st
import requests
import pandas as pd
from streamlit_echarts import st_echarts
import numpy as np
from scipy.stats import poisson

API_URL = "https://mundial-2026-analytics-production.up.railway.app"
RONDAS = ["Group stage", "Round of 32", "Round of 16", "Quarterfinal", "Semifinal", "3rd place", "Final"]
RONDAS_BRACKET = ["Round of 16", "Quarterfinal", "Semifinal", "Final"]

FLAG_CDN = "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3"

ISO_PAISES = {
    "Algeria": "dz", "Argentina": "ar", "Australia": "au", "Austria": "at",
    "Belgium": "be", "Bosnia and Herzegovina": "ba", "Brazil": "br", "Cabo Verde": "cv",
    "Canada": "ca", "Colombia": "co", "Congo DR": "cd", "Croatia": "hr",
    "Curaçao": "cw", "Czechia": "cz", "Côte d'Ivoire": "ci", "Ecuador": "ec",
    "Egypt": "eg", "England": "gb-eng", "France": "fr", "Germany": "de",
    "Ghana": "gh", "Haiti": "ht", "IR Iran": "ir", "Iraq": "iq",
    "Japan": "jp", "Jordan": "jo", "Korea Republic": "kr", "Mexico": "mx",
    "Morocco": "ma", "Netherlands": "nl", "New Zealand": "nz", "Norway": "no",
    "Panama": "pa", "Paraguay": "py", "Portugal": "pt", "Qatar": "qa",
    "Saudi Arabia": "sa", "Scotland": "gb-sct", "Senegal": "sn", "South Africa": "za",
    "Spain": "es", "Sweden": "se", "Switzerland": "ch", "Tunisia": "tn",
    "Türkiye": "tr", "United States": "us", "Uruguay": "uy", "Uzbekistan": "uz",
}


def con_bandera(equipo):
    codigo = ISO_PAISES.get(equipo)
    if not codigo:
        return equipo
    return (f'<img src="{FLAG_CDN}/{codigo}.svg" width="20" '
            f'style="vertical-align:middle;margin-right:6px;border-radius:2px;">' + equipo)


st.set_page_config(page_title="Mundial 2026 - Analytics", layout="wide", page_icon=":soccer:")

ACCENT = "#3b82f6"

st.markdown(f"""
<style>
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    div[data-testid="stMetric"] {{
        background-color: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.08);
        border-left: 3px solid {ACCENT};
        border-radius: 8px;
        padding: 14px 18px;
    }}
    div[data-testid="stMetricValue"] {{ font-size: 1.6rem; font-weight: 700; }}
    div[data-testid="stMetricLabel"] {{ font-size: 0.78rem; opacity: 0.65; text-transform: uppercase; letter-spacing: 0.04em; }}
    .rank-badge {{
        display: inline-flex; align-items: center; justify-content: center;
        width: 28px; height: 28px; border-radius: 50%;
        background: linear-gradient(135deg, {ACCENT}, #1e3a5f);
        color: white; font-size: 0.85rem; font-weight: 700;
        margin-right: 12px;
    }}
    .live-tag {{
        font-size: 0.65rem; font-weight: 700; letter-spacing: 0.05em;
        background-color: rgba(220,50,50,0.15); color: #ff6b6b;
        border-radius: 4px; padding: 2px 7px; margin-left: 8px;
    }}
    .bracket-pair {{
        border-left: 2px solid rgba(255,255,255,0.15);
        padding-left: 10px; margin-bottom: 14px; margin-left: 4px;
    }}
    .bracket-card {{
        background-color: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
    }}
    .bracket-card.live {{ border-color: #ff6b6b; background-color: rgba(220,50,50,0.06); }}
    .bracket-team {{ display: flex; justify-content: space-between; padding: 3px 0; }}
    .bracket-team.winner {{ font-weight: 700; }}
    .bracket-date {{ font-size: 0.7rem; opacity: 0.5; margin-bottom: 4px; }}
    h1 {{ font-weight: 700; letter-spacing: -0.02em; }}
    h1 span.accent {{ color: {ACCENT}; }}
    h2, h3, h4 {{ font-weight: 600; }}
    hr {{ margin: 1rem 0; opacity: 0.12; }}
    .app-footer {{
        margin-top: 4rem; padding-top: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.08);
        font-size: 0.8rem; opacity: 0.6; text-align: center;
    }}
    .app-footer a {{ color: {ACCENT}; text-decoration: none; }}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>Mundial 2026 <span class='accent'>—</span> Panel de Datos</h1>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["Stats", "Bracket", "Predicciones", "En vivo"])


def ronda_por_defecto(rondas_con_data):
    for r in reversed(RONDAS):
        if r in rondas_con_data:
            return r
    return RONDAS[0]


CATEGORIAS = {
    "Goleadores": {"endpoint": "/goleadores", "live_key": "goles_partido", "col": "Goles"},
    "Asistencias": {"endpoint": "/asistencias", "live_key": "asistencias_partido", "col": "Asistencias"},
    "Tarjetas amarillas": {"endpoint": "/tarjetas-amarillas", "live_key": "amarillas_partido", "col": "Tarjetas amarillas"},
    "Tarjetas rojas": {"endpoint": "/tarjetas-rojas", "live_key": "rojas_partido", "col": "Tarjetas rojas"},
}

# ================= TAB 1: STATS =================
with tab1:
    st.subheader("Analitica general")

    resp_kpi = requests.get(f"{API_URL}/kpis-torneo")
    if resp_kpi.status_code == 200:
        kpis = resp_kpi.json()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Partidos jugados", kpis["partidos_jugados"])
        k2.metric("Goles totales", kpis["total_goles"])
        k3.metric("Goles por partido", kpis["promedio_goles_partido"])
        k4.metric("Goleadores distintos", kpis["goleadores_distintos"])

    resp_barras = requests.get(f"{API_URL}/goles-por-equipo")
    if resp_barras.status_code == 200 and resp_barras.json():
        data_eq = [d for d in resp_barras.json() if d.get("total_goles")]
        data_eq = sorted(data_eq, key=lambda d: d["total_goles"], reverse=True)[:15]
        data_eq = list(reversed(data_eq))  # para que el mayor quede arriba en barra horizontal

        equipos = [d["team"] for d in data_eq]
        valores = [int(d["total_goles"]) for d in data_eq]

        opciones_barras = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"left": "20%", "right": "5%", "top": "5%", "bottom": "5%"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": equipos},
            "series": [{
                "type": "bar",
                "data": valores,
                "itemStyle": {"color": "#3b82f6"},
                "label": {"show": True, "position": "right"},
            }],
        }
        st.markdown("##### Top 15 equipos por goles (todo el torneo)")
        st_echarts(options=opciones_barras, height="420px")
    else:
        st.info("No se pudo cargar el grafico de goles por equipo.")

    col_donut, col_scatter = st.columns(2)

    with col_donut:
        resp_ronda = requests.get(f"{API_URL}/goles-por-ronda")
        if resp_ronda.status_code == 200 and resp_ronda.json():
            data_ronda = [d for d in resp_ronda.json() if d.get("total_goles") and d.get("round")]
            donut_data = [{"name": d["round"], "value": int(d["total_goles"])} for d in data_ronda]

            opciones_donut = {
                "tooltip": {"trigger": "item", "formatter": "{b}: {c} goles ({d}%)"},
                "legend": {"bottom": "0%", "textStyle": {"color": "#ccc"}},
                "series": [{
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "data": donut_data,
                    "label": {"formatter": "{b}\n{c}"},
                }],
            }
            st.markdown("##### Goles por ronda")
            st_echarts(options=opciones_donut, height="380px")

    with col_scatter:
        resp_efic = requests.get(f"{API_URL}/eficiencia-equipos", params={"limit": 20})
        if resp_efic.status_code == 200 and resp_efic.json():
            data_efic = resp_efic.json()
            scatter_data = []
            for d in data_efic:
                if not d.get("total_tiros"):
                    continue
                tiros = int(d["total_tiros"])
                goles = int(d["total_goles"])
                tiros_arco = int(d["total_tiros_arco"] or 0)
                tamano = max(10, min(60, tiros_arco))
                scatter_data.append({
                    "name": d["team"],
                    "value": [tiros, goles],
                    "symbolSize": tamano,
                })

            opciones_scatter = {
                "tooltip": {"formatter": "{b}: {c}"},
                "xAxis": {"name": "Remates totales", "nameLocation": "middle", "nameGap": 30},
                "yAxis": {"name": "Goles", "nameLocation": "middle", "nameGap": 30},
                "series": [{
                    "type": "scatter",
                    "data": scatter_data,
                    "itemStyle": {"color": "#3b82f6", "opacity": 0.75},
                }],
            }
            st.markdown("##### Eficiencia: remates vs goles por equipo (tamano = remates al arco)")
            st_echarts(options=opciones_scatter, height="380px")

    st.divider()
    st.subheader("Equipos en Cuartos de Final")

    EQUIPOS_CUARTOS = ["France", "Morocco", "Spain", "Belgium", "Norway", "England", "Argentina", "Switzerland"]
    equipos_param = ",".join(EQUIPOS_CUARTOS)
    resp_qf = requests.get(f"{API_URL}/stats-promedio-equipos", params={"equipos": equipos_param})

    if resp_qf.status_code == 200 and resp_qf.json():
        data_qf = resp_qf.json()
        st.caption("Corners y faltas no se muestran: no se guardan historicamente por equipo, solo durante el analisis en vivo.")

        col_bar, col_radar = st.columns(2)

        with col_bar:
            data_ordenada = sorted(data_qf, key=lambda d: d["avg_goles"], reverse=True)
            equipos_nombres = [d["team"] for d in reversed(data_ordenada)]
            valores_goles = [d["avg_goles"] for d in reversed(data_ordenada)]

            opciones_bar_qf = {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "25%", "right": "10%"},
                "xAxis": {"type": "value", "name": "Goles/partido"},
                "yAxis": {"type": "category", "data": equipos_nombres},
                "series": [{
                    "type": "bar", "data": valores_goles,
                    "itemStyle": {"color": "#3b82f6"}, "label": {"show": True, "position": "right"},
                }],
            }
            st.markdown("##### Promedio de goles por partido")
            st_echarts(options=opciones_bar_qf, height="360px")

        with col_radar:
            max_goles = max((d["avg_goles"] for d in data_qf), default=1) or 1
            max_tiros = max((d["avg_tiros"] for d in data_qf), default=1) or 1
            max_tiros_arco = max((d["avg_tiros_arco"] for d in data_qf), default=1) or 1
            max_amarillas = max((d["avg_amarillas"] for d in data_qf), default=1) or 1
            max_rojas = max((d["avg_rojas"] for d in data_qf), default=0.5) or 0.5

            indicadores = [
                {"name": "Goles", "max": round(max_goles * 1.2, 1)},
                {"name": "Remates", "max": round(max_tiros * 1.2, 1)},
                {"name": "Remates al arco", "max": round(max_tiros_arco * 1.2, 1)},
                {"name": "Tarjetas amarillas", "max": round(max_amarillas * 1.2, 1)},
                {"name": "Tarjetas rojas", "max": round(max_rojas * 1.2 + 0.5, 1)},
            ]

            colores = ["#3b82f6", "#ef4444", "#22c55e", "#eab308", "#a855f7", "#06b6d4", "#f97316", "#ec4899"]
            series_radar = []
            for i, d in enumerate(data_qf):
                series_radar.append({
                    "value": [d["avg_goles"], d["avg_tiros"], d["avg_tiros_arco"], d["avg_amarillas"], d["avg_rojas"]],
                    "name": d["team"],
                    "lineStyle": {"color": colores[i % len(colores)]},
                    "itemStyle": {"color": colores[i % len(colores)]},
                    "areaStyle": {"opacity": 0.05},
                })

            opciones_radar = {
                "tooltip": {},
                "legend": {"bottom": "0%", "textStyle": {"color": "#ccc"}, "type": "scroll"},
                "radar": {"indicator": indicadores, "radius": "60%"},
                "series": [{"type": "radar", "data": series_radar}],
            }
            st.markdown("##### Perfil comparativo (los 8 equipos)")
            st_echarts(options=opciones_radar, height="400px")

        st.dataframe(pd.DataFrame(data_qf), use_container_width=True, hide_index=True)
    else:
        st.info("No hay suficientes datos todavia para los equipos de cuartos.")

    st.divider()
    st.subheader("Estadísticas de jugadores")
    col_cat, col_limit = st.columns([2, 1])
    categoria = col_cat.selectbox("Categoría", list(CATEGORIAS.keys()))
    limit = col_limit.slider("Cantidad", 5, 30, 10)

    cfg = CATEGORIAS[categoria]

    @st.fragment(run_every=30)
    def mostrar_stats():
        resp = requests.get(f"{API_URL}{cfg['endpoint']}", params={"limit": limit})
        if not (resp.status_code == 200 and resp.json()):
            st.warning("No hay datos disponibles todavía para esta categoría.")
            return

        raw = resp.json()
        df = pd.DataFrame(raw)
        df.columns = ["Jugador", "Equipo", cfg["col"]]
        df["En vivo"] = False

        home_live = st.session_state.get("live_home")
        away_live = st.session_state.get("live_away")
        aviso = None
        if home_live and away_live:
            resp_live = requests.get(f"{API_URL}/live", params={"home": home_live, "away": away_live})
            if resp_live.status_code == 200 and not resp_live.json().get("error"):
                eventos = resp_live.json().get(cfg["live_key"], [])
                for ev in eventos:
                    jugador, equipo = ev["player"], ev["team"]
                    match_row = df["Jugador"] == jugador
                    if match_row.any():
                        df.loc[match_row, cfg["col"]] += 1
                        df.loc[match_row, "En vivo"] = True
                    else:
                        nueva = pd.DataFrame([{"Jugador": jugador, "Equipo": equipo, cfg["col"]: 1, "En vivo": True}])
                        df = pd.concat([df, nueva], ignore_index=True)
                df = df.sort_values(cfg["col"], ascending=False).reset_index(drop=True)
                if eventos:
                    aviso = f"Incluye eventos en vivo de {home_live} vs {away_live}, aún no sincronizados en la base."

        if aviso:
            st.caption(aviso)

        for i in range(min(3, len(df))):
            fila = df.iloc[i]
            tag = "<span class='live-tag'>LIVE</span>" if fila["En vivo"] else ""
            col1, col2 = st.columns([4, 1])
            col1.markdown(
                f"<span class='rank-badge'>{i+1}</span>"
                f"<strong>{fila['Jugador']}</strong> — {fila['Equipo']}{tag}",
                unsafe_allow_html=True,
            )
            col2.markdown(f"<div style='text-align:right; font-weight:600;'>{fila[cfg['col']]}</div>", unsafe_allow_html=True)

        st.divider()
        df_mostrar = df.drop(columns=["En vivo"])
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        st.bar_chart(df_mostrar.set_index("Jugador")[cfg["col"]])

    mostrar_stats()

# ================= TAB 2: BRACKET =================

def ganador_partido(home_team, away_team, score):
    if not score or not score.strip():
        return None
    s = score.replace("–", "-").strip()
    if "(" in s:
        import re
        penales = re.findall(r"\((\d+)\)", s)
        if len(penales) == 2:
            return home_team if int(penales[0]) > int(penales[1]) else away_team
    partes = s.replace("(", "").replace(")", "").split("-")
    partes = [p.strip() for p in partes if p.strip()]
    if len(partes) == 2:
        try:
            gh, ga = int(partes[0].split()[-1]), int(partes[1].split()[0])
            if gh > ga:
                return home_team
            elif ga > gh:
                return away_team
        except (ValueError, IndexError):
            return None
    return None


def encontrar_feeder_index(equipo, ronda_anterior):
    for i, m in enumerate(ronda_anterior):
        ganador = ganador_partido(m["home_team"], m["away_team"], m.get("score"))
        if ganador == equipo or (ganador is None and equipo in (m["home_team"], m["away_team"])):
            return i
    return None


def ordenar_por_linaje(partidos_ronda, ronda_anterior):
    if not ronda_anterior:
        return partidos_ronda
    con_indice = []
    for m in partidos_ronda:
        idx_home = encontrar_feeder_index(m["home_team"], ronda_anterior)
        idx_away = encontrar_feeder_index(m["away_team"], ronda_anterior)
        idxs = [i for i in (idx_home, idx_away) if i is not None]
        orden = sum(idxs) / len(idxs) if idxs else 999
        con_indice.append((orden, m))
    con_indice.sort(key=lambda x: x[0])
    return [m for _, m in con_indice]


def renderizar_tarjeta(p, data_live, home_live, away_live):
    es_vivo = (
        data_live and home_live and away_live and
        {p["home_team"], p["away_team"]} & {home_live, away_live}
        and not (p["score"] and p["score"].strip())
    )
    clase = "bracket-card live" if es_vivo else "bracket-card"

    if es_vivo:
        g_home, g_away = data_live["marcador"].split("-")
        fecha_txt = f"EN VIVO - {data_live['minuto']}'"
    elif p["score"] and p["score"].strip():
        marcador_partes = p["score"].replace("–", "-").split("-")
        g_home = marcador_partes[0].strip() if len(marcador_partes) == 2 else "-"
        g_away = marcador_partes[1].strip() if len(marcador_partes) == 2 else "-"
        fecha_txt = str(p["date"])[:10] if p.get("date") else ""
    else:
        g_home, g_away = "-", "-"
        fecha_txt = str(p["date"])[:10] if p.get("date") else "Por definir"

    ganador = ganador_partido(p["home_team"], p["away_team"], p.get("score")) if not es_vivo else None
    clase_home = "bracket-team winner" if ganador == p["home_team"] else "bracket-team"
    clase_away = "bracket-team winner" if ganador == p["away_team"] else "bracket-team"

    return f"""
    <div class="{clase}">
        <div class="bracket-date">{fecha_txt}</div>
        <div class="{clase_home}"><span>{con_bandera(p['home_team'])}</span><span>{g_home}</span></div>
        <div class="{clase_away}"><span>{con_bandera(p['away_team'])}</span><span>{g_away}</span></div>
    </div>
    """


with tab2:
    st.subheader("Cuadro del torneo")
    st.caption("El borde vertical agrupa los partidos que alimentan al siguiente cruce.")

    home_live = st.session_state.get("live_home")
    away_live = st.session_state.get("live_away")

    @st.fragment(run_every=30)
    def mostrar_bracket():
        data_live = None
        if home_live and away_live:
            resp_live = requests.get(f"{API_URL}/live", params={"home": home_live, "away": away_live})
            if resp_live.status_code == 200 and not resp_live.json().get("error"):
                data_live = resp_live.json()

        partidos_por_ronda = {}
        for ronda in RONDAS_BRACKET:
            resp = requests.get(f"{API_URL}/bracket/{ronda}")
            partidos_por_ronda[ronda] = resp.json() if resp.status_code == 200 else []

        ronda_anterior = None
        for ronda in RONDAS_BRACKET:
            partidos_por_ronda[ronda] = ordenar_por_linaje(partidos_por_ronda[ronda], ronda_anterior)
            ronda_anterior = partidos_por_ronda[ronda]

        cols = st.columns(len(RONDAS_BRACKET))
        for i, ronda in enumerate(RONDAS_BRACKET):
            with cols[i]:
                st.markdown(f"**{ronda}**")
                partidos = partidos_por_ronda[ronda]

                if not partidos:
                    st.caption("Sin partidos definidos todavia.")
                    continue

                CARD_HEIGHT = 92  # alto aprox. de cada tarjeta en px, ajustable si no calza

                if i == 0:
                    html = "".join(renderizar_tarjeta(p, data_live, home_live, away_live) for p in partidos)
                    st.markdown(html, unsafe_allow_html=True)
                else:
                    top_anterior = None
                    for j, p in enumerate(partidos):
                        # centro del elemento j en la ronda i, segun formula de bracket binario
                        centro = CARD_HEIGHT * (2 ** i) * (j + 0.5)
                        top = centro - CARD_HEIGHT / 2
                        margen = top if top_anterior is None else (top - top_anterior - CARD_HEIGHT)
                        margen = max(0, margen)
                        top_anterior = top

                        html_card = renderizar_tarjeta(p, data_live, home_live, away_live)
                        st.markdown(
                            f'<div class="bracket-pair" style="margin-top:{margen}px;">{html_card}</div>',
                            unsafe_allow_html=True,
                        )

    mostrar_bracket()

# ================= TAB 3: PREDICCIONES =================
with tab3:
    st.subheader("Predicciones del modelo Poisson")

    ronda_pred = st.selectbox("Ronda a predecir", RONDAS, index=RONDAS.index("Quarterfinal"), key="ronda_pred")

    resp = requests.get(f"{API_URL}/predicciones", params={"limit": 20, "ronda": ronda_pred})
    if resp.status_code == 200 and resp.json():
        data = resp.json()
        for p in data:
            with st.container(border=True):
                st.markdown(f"#### {p['home_team']} vs {p['away_team']}")
                if p.get("round"):
                    st.caption(p["round"])

                col1, col2, col3 = st.columns(3)
                col1.metric(p["home_team"], f"{p['prob_local']*100:.1f}%")
                col2.metric("Empate", f"{p['prob_empate']*100:.1f}%")
                col3.metric(p["away_team"], f"{p['prob_visitante']*100:.1f}%")

                col4, col5 = st.columns(2)
                if p.get("over25") is not None:
                    col4.metric("Over 2.5 goles", f"{p['over25']*100:.1f}%")
                if p.get("btts") is not None:
                    col5.metric("Ambos anotan", f"{p['btts']*100:.1f}%")

                detalle = p.get("detalle") or {}

                info_partes = []
                if detalle.get("sede"):
                    info_partes.append(detalle["sede"])
                if detalle.get("altitud_m") is not None:
                    info_partes.append(f"{detalle['altitud_m']:.0f}m altitud")
                if detalle.get("temp_prom_c") is not None:
                    info_partes.append(f"{detalle['temp_prom_c']}°C promedio")
                if detalle.get("arbitro"):
                    info_partes.append(f"Árbitro: {detalle['arbitro']}")
                if info_partes:
                    st.caption(" · ".join(info_partes))

                grilla = detalle.get("grilla_completa")
                if grilla:
                    with st.expander("Mapa de calor de marcadores"):
                        df_grilla = pd.DataFrame(grilla)
                        max_goles = 5
                        df_grilla = df_grilla[
                            (df_grilla["goles_local"] <= max_goles) & (df_grilla["goles_visit"] <= max_goles)
                        ]
                        pivot = df_grilla.pivot(index="goles_local", columns="goles_visit", values="prob")
                        pivot = pivot.sort_index(ascending=False)
                        st.caption(f"Filas: goles {p['home_team']} · Columnas: goles {p['away_team']}")
                        st.dataframe(
                            pivot.style.format("{:.1%}").background_gradient(cmap="Greens", axis=None),
                            use_container_width=True,
                        )

                marcadores_top = detalle.get("marcadores_top")
                if marcadores_top:
                    with st.expander("Top 5 marcadores más probables"):
                        df_top = pd.DataFrame(marcadores_top)
                        df_top["Marcador"] = df_top.apply(
                            lambda r: f"{p['home_team']} {int(r['goles_local'])} - {int(r['goles_visit'])} {p['away_team']}",
                            axis=1
                        )
                        df_top["Prob."] = df_top["prob"].apply(lambda x: f"{x*100:.1f}%")
                        st.dataframe(df_top[["Marcador", "Prob."]], use_container_width=True, hide_index=True)

                mercados = [
                    ("Remates totales", detalle.get("lambda_remates")),
                    ("Remates al arco", detalle.get("lambda_remates_arco")),
                    ("Corners", detalle.get("lambda_corners")),
                    ("Tarjetas amarillas", p.get("lambda_tarjetas")),
                    ("Faltas", p.get("lambda_faltas")),
                ]
                mercados = [(nombre, lam) for nombre, lam in mercados if lam is not None]
                if mercados:
                    with st.expander("Otros mercados (Over/Under)"):
                        filas_mercado = []
                        for nombre, lam in mercados:
                            linea = round(lam) - 0.5
                            p_over = 1 - poisson.cdf(np.floor(linea), lam)
                            filas_mercado.append({
                                "Mercado": nombre, "Lambda": f"{lam:.2f}", "Línea": linea,
                                "Over": f"{p_over*100:.1f}%", "Under": f"{(1-p_over)*100:.1f}%",
                            })
                        st.dataframe(pd.DataFrame(filas_mercado), use_container_width=True, hide_index=True)
    else:
        st.warning(f"No hay predicciones guardadas todavía para {ronda_pred}.")

# ================= TAB 4: EN VIVO =================
with tab4:
    st.subheader("Análisis en vivo")
    PROXIMOS_CUARTOS = [
        ("España", "Bélgica"), ("Noruega", "Inglaterra"), ("Argentina", "Suiza"),
    ]

    if st.button("Buscar proximo partido en vivo"):
        encontrado = None
        for h, a in PROXIMOS_CUARTOS:
            r = requests.get(f"{API_URL}/live", params={"home": h, "away": a})
            if r.status_code == 200:
                d = r.json()
                if not d.get("error") and not d.get("finalizado"):
                    encontrado = (h, a)
                    break
        if encontrado:
            st.session_state["live_home_default"] = encontrado[0]
            st.session_state["live_away_default"] = encontrado[1]
            st.rerun()
        else:
            st.info("Ninguno de los cuartos restantes esta en vivo todavia.")

    col_a, col_b = st.columns(2)
    default_home = st.session_state.get("live_home_default", "Francia")
    default_away = st.session_state.get("live_away_default", "Marruecos")
    home_input = col_a.text_input("Equipo local (en español)", value=default_home)
    away_input = col_b.text_input("Equipo visita (en español)", value=default_away)
    st.session_state["live_home"] = home_input
    st.session_state["live_away"] = away_input

    @st.fragment(run_every=30)
    def mostrar_vivo():
        resp = requests.get(f"{API_URL}/live", params={"home": home_input, "away": away_input})
        if resp.status_code != 200:
            st.error("No se pudo conectar con el endpoint /live.")
            return
        data = resp.json()
        if data.get("error"):
            st.warning(data["error"])
            return

        goles_home, goles_away = data["marcador"].split("-")
        st.markdown(f"### 🏟️ {home_input} {goles_home} - {goles_away} {away_input}")
        st.caption(f"⏱️ Minuto {data['minuto']}' ({data.get('period','')}) · se actualiza cada 30s")

        etiquetas = {
            "remates": "🎯 Remates totales", "remates_arco": "🥅 Remates al arco",
            "corners": "🚩 Corners", "tarjetas_amarillas": "🟨 Tarjetas amarillas", "faltas": "⚠️ Faltas",
        }
        filas = []
        for key, nombre in etiquetas.items():
            actual = data["actuales"].get(key, 0)
            proy = data["proyecciones"].get(key)
            filas.append({
                "Métrica": nombre, "Actual": actual,
                "Proyección final": f"{proy:.1f}" if proy is not None else "N/D",
            })

        if not data["tiene_prematch"]:
            st.info("No hay predicción pre-match guardada para comparar — solo datos en vivo.")

        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    mostrar_vivo()

st.markdown("""
<div class="app-footer">
    Desarrollado por Smith Eusebio Lino Moreno &middot;
    <a href="https://www.linkedin.com/in/slino-moreno/" target="_blank">LinkedIn</a> &middot;
    Datos: elnine.com.ar &middot; Mundial 2026
</div>
""", unsafe_allow_html=True)
