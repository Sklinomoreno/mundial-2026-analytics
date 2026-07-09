import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

HEADERS_ELNINE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://elnine.com.ar",
}

EQUIPOS_MAP = {
    "Argelia": "Algeria", "Argentina": "Argentina", "Australia": "Australia",
    "Austria": "Austria", "Bélgica": "Belgium", "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Brasil": "Brazil", "Islas Cabo Verde": "Cabo Verde", "Canadá": "Canada",
    "Colombia": "Colombia", "RD Congo": "Congo DR", "Croacia": "Croatia",
    "Curazao": "Curaçao", "República Checa": "Czechia", "Costa de Marfil": "Côte d'Ivoire",
    "Ecuador": "Ecuador", "Egipto": "Egypt", "Inglaterra": "England",
    "Francia": "France", "Alemania": "Germany", "Ghana": "Ghana",
    "Haití": "Haiti", "Irán": "IR Iran", "Irak": "Iraq", "Japón": "Japan",
    "Jordania": "Jordan", "Corea del Sur": "Korea Republic", "México": "Mexico",
    "Marruecos": "Morocco", "Holanda": "Netherlands", "Países Bajos": "Netherlands",
    "Nueva Zelanda": "New Zealand", "Noruega": "Norway", "Panamá": "Panama",
    "Paraguay": "Paraguay", "Portugal": "Portugal", "Qatar": "Qatar",
    "Arabia Saudita": "Saudi Arabia", "Escocia": "Scotland", "Senegal": "Senegal",
    "Sudáfrica": "South Africa", "España": "Spain", "Suecia": "Sweden",
    "Suiza": "Switzerland", "Túnez": "Tunisia", "Turquía": "Türkiye",
    "Estados Unidos": "United States", "Uruguay": "Uruguay", "Uzbekistán": "Uzbekistan",
}

def buscar_match_id_hoy(home_es, away_es, dias_atras=3):
    from datetime import datetime, timedelta
    hoy = datetime.now()
    for delta in range(dias_atras):
        fecha = (hoy - timedelta(days=delta)).strftime("%Y-%m-%d")
        url = f"https://api.elnine.com.ar/schedule?date={fecha}"
        headers = {**HEADERS_ELNINE, "Referer": "https://elnine.com.ar/"}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception:
            continue
        for m in data.get("matches", []):
            if m.get("tournamentCalendarSlug") != "fifa-world-cup":
                continue
            h, a = m["homeTeam"]["name"], m["awayTeam"]["name"]
            if (h == home_es and a == away_es) or (h == away_es and a == home_es):
                return m["id"], fecha
    return None, None

def obtener_partido_completo(match_id):
    url = f"https://api.elnine.com.ar/match/{match_id}"
    headers = {**HEADERS_ELNINE, "Referer": f"https://elnine.com.ar/partido/{match_id}"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()["matchDetail"]

def obtener_estado_vivo(match_id):
    """Combina /stats (numeros) y /match/{id} (minuto/periodo real) -- igual que en el notebook."""
    url_stats = f"https://api.elnine.com.ar/match/{match_id}/stats"
    headers = {**HEADERS_ELNINE, "Referer": f"https://elnine.com.ar/partido/{match_id}"}
    r = requests.get(url_stats, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    stats_dict = {item["label"]: item for item in data.get("stats", [])}

    detalle = obtener_partido_completo(match_id)

    period = detalle.get("period")
    minuto = detalle.get("minute")

    if period == "HT":
        minutos_jugados = 45
    elif minuto:
        minutos_jugados = minuto
    elif period == "FT":
        minutos_jugados = 90
    else:
        minutos_jugados = 1

    return {
        "period": period, "minutos_jugados": minutos_jugados,
        "score_home": detalle["homeTeam"]["score"], "score_away": detalle["awayTeam"]["score"],
        "stats": stats_dict,
    }

def obtener_prediccion_guardada(home_es, away_es):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT lambda_tarjetas, lambda_faltas, detalle
        FROM predicciones
        WHERE (home_team = %s AND away_team = %s) OR (home_team = %s AND away_team = %s)
        ORDER BY fecha_prediccion DESC LIMIT 1
    """, (home_es, away_es, away_es, home_es))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    lambda_tarjetas, lambda_faltas, detalle = row
    lam_goles_pre = 0
    if detalle and detalle.get("grilla_completa"):
        for celda in detalle["grilla_completa"]:
            lam_goles_pre += celda["prob"] * (celda["goles_local"] + celda["goles_visit"])

    def a_float(v):
        return float(v) if v is not None else None

    return {
        "lam_goles": a_float(lam_goles_pre),
        "lam_remates": a_float(detalle.get("lambda_remates")) if detalle else None,
        "lam_remates_arco": a_float(detalle.get("lambda_remates_arco")) if detalle else None,
        "lam_corners": a_float(detalle.get("lambda_corners")) if detalle else None,
        "lam_tarjetas": a_float(lambda_tarjetas), "lam_faltas": a_float(lambda_faltas),
    }

def proyectar(valor_actual, minutos_jugados, lam_pre_total, peso_maximo_vivo=0.85):
    if minutos_jugados <= 0 or lam_pre_total is None:
        return lam_pre_total
    minutos_restantes = max(90 - minutos_jugados, 0)
    peso_vivo = min(peso_maximo_vivo, minutos_jugados / 90)
    rate_observado = valor_actual / minutos_jugados
    proyeccion_vivo = valor_actual + rate_observado * minutos_restantes
    proyeccion_pre = valor_actual + (lam_pre_total * minutos_restantes / 90)
    return peso_vivo * proyeccion_vivo + (1 - peso_vivo) * proyeccion_pre

def obtener_analisis_vivo(home_es, away_es):
    match_id, fecha = buscar_match_id_hoy(home_es, away_es)
    if not match_id:
        return {"error": f"No se encontro el partido {home_es} vs {away_es} en los ultimos dias."}

    estado = obtener_estado_vivo(match_id)
    stats_dict = estado["stats"]
    minuto = estado["minutos_jugados"]

    def val(label):
        item = stats_dict.get(label)
        return (item.get("home", 0) + item.get("away", 0)) if item else 0

    def val_lado(label, lado):
        item = stats_dict.get(label)
        return item.get(lado, 0) if item else 0

    actuales = {
        "remates": val("Total remates"),
        "remates_arco": val("Remates al arco"),
        "corners": val("Saques de esquina"),
        "tarjetas_amarillas": val("Tarjetas amarillas"),
        "faltas": val("Faltas"),
    }

    metricas_equipo = ["Total remates", "Remates al arco", "Saques de esquina",
                        "Tarjetas amarillas", "Tarjetas rojas", "Faltas"]
    actuales_por_equipo = {
        "home": {m: val_lado(m, "home") for m in metricas_equipo},
        "away": {m: val_lado(m, "away") for m in metricas_equipo},
    }

    pre = obtener_prediccion_guardada(home_es, away_es)

    proyecciones = {}
    if pre:
        proyecciones = {
            "remates": proyectar(actuales["remates"], minuto, pre["lam_remates"]),
            "remates_arco": proyectar(actuales["remates_arco"], minuto, pre["lam_remates_arco"]),
            "corners": proyectar(actuales["corners"], minuto, pre["lam_corners"]),
            "tarjetas_amarillas": proyectar(actuales["tarjetas_amarillas"], minuto, pre["lam_tarjetas"]),
            "faltas": proyectar(actuales["faltas"], minuto, pre["lam_faltas"]),
        }

    eventos = obtener_eventos_partido(match_id, home_es, away_es)

    if estado["period"] == "FT":
        return {
            "error": (f"{home_es} {estado['score_home']}-{estado['score_away']} {away_es} ya finalizo. "
                       f"Corre sync_calendario.py y sync_goleadores.py para actualizar la base con el resultado final."),
            "finalizado": True,
        }

    return {
        "minuto": minuto, "period": estado["period"],
        "marcador": f"{estado['score_home']}-{estado['score_away']}",
        "match_id": match_id,
        "actuales": actuales, "proyecciones": proyecciones, "tiene_prematch": pre is not None,
        "goles_partido": eventos["goles"],
        "asistencias_partido": eventos["asistencias"],
        "amarillas_partido": eventos["amarillas"],
        "rojas_partido": eventos["rojas"],
        "actuales_por_equipo": actuales_por_equipo,
        "finalizado": False,
    }


def obtener_eventos_partido(match_id, home_es, away_es):
    """Extrae goles, asistencias y tarjetas del partido en curso desde los events.
    Devuelve un dict con 4 listas, cada una de {player, team, minuto}."""
    home_en = EQUIPOS_MAP.get(home_es, home_es)
    away_en = EQUIPOS_MAP.get(away_es, away_es)
    try:
        detalle = obtener_partido_completo(match_id)
    except Exception:
        return {"goles": [], "asistencias": [], "amarillas": [], "rojas": []}

    goles, asistencias, amarillas, rojas = [], [], [], []
    for e in detalle.get("events", []):
        equipo = home_en if e.get("team") == "home" else away_en
        tipo = e.get("type")
        if tipo in ("goal", "goal-penalty"):
            goles.append({"player": e.get("playerNameFull"), "team": equipo, "minuto": e.get("minute")})
            if e.get("assistFull"):
                asistencias.append({"player": e.get("assistFull"), "team": equipo, "minuto": e.get("minute")})
        elif tipo == "yellow":
            amarillas.append({"player": e.get("playerNameFull"), "team": equipo, "minuto": e.get("minute")})
        elif tipo == "red":
            rojas.append({"player": e.get("playerNameFull"), "team": equipo, "minuto": e.get("minute")})

    return {"goles": goles, "asistencias": asistencias, "amarillas": amarillas, "rojas": rojas}
