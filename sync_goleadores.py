"""
Sincroniza goles/asistencias reales (desde elnine.com.ar) hacia jugadores_stats.
Compara nombres de jugador y equipo ignorando acentos/mayúsculas.
"""
import os
import time
import unicodedata
import difflib
import requests
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

HEADERS_ELNINE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://elnine.com.ar",
}

# Mapeo español (elnine) -> nombre EXACTO en tu tabla (48 equipos)
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

def normalizar(texto):
    """Quita acentos y pasa a minúsculas para comparar sin errores de tildes."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def buscar_jugador_similar(nombre_buscado, game_id, jugadores_db, umbral=0.75):
    """Si no hay match exacto, busca el jugador mas parecido dentro del MISMO partido."""
    nombre_norm = normalizar(nombre_buscado)
    candidatos = [
        (clave, nombre_real) for clave, nombre_real in jugadores_db.items()
        if clave[0] == game_id
    ]
    mejor_score, mejor_nombre = 0, None
    for (gid, nombre_db_norm), nombre_real in candidatos:
        # Caso apodo corto: una de las dos formas es una sola palabra contenida en la otra
        palabras_buscado = nombre_norm.split()
        palabras_db = nombre_db_norm.split()
        if len(palabras_buscado) == 1 and palabras_buscado[0] in palabras_db:
            return nombre_real, 1.0
        if len(palabras_db) == 1 and palabras_db[0] in palabras_buscado:
            return nombre_real, 1.0
        score = difflib.SequenceMatcher(None, nombre_norm, nombre_db_norm).ratio()
        if score > mejor_score:
            mejor_score, mejor_nombre = score, nombre_real
    if mejor_score >= umbral:
        return mejor_nombre, mejor_score
    return None, mejor_score

def obtener_partidos_fecha(fecha_str):
    url = f"https://api.elnine.com.ar/schedule?date={fecha_str}"
    headers = {**HEADERS_ELNINE, "Referer": "https://elnine.com.ar/"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Error en {fecha_str}: {e}")
        return []
    return [
        {"id": m["id"], "home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
         "status": m.get("status"), "date": fecha_str}
        for m in data.get("matches", [])
        if m.get("tournamentCalendarSlug") == "fifa-world-cup"
    ]

def obtener_partido_completo(match_id):
    url = f"https://api.elnine.com.ar/match/{match_id}"
    headers = {**HEADERS_ELNINE, "Referer": f"https://elnine.com.ar/partido/{match_id}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()["matchDetail"]
    except Exception as e:
        print(f"Error match {match_id}: {e}")
        return None

def main():
    print("Descargando fixture del Mundial...")
    fechas = pd.date_range("2026-06-11", pd.Timestamp.today()).strftime("%Y-%m-%d").tolist()
    partidos = []
    for f in fechas:
        partidos.extend(obtener_partidos_fecha(f))
        time.sleep(0.8)

    finalizados = [p for p in partidos if p["status"] == "finished"]
    print(f"{len(finalizados)} partidos finalizados encontrados.\n")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()

    # Traemos TODOS los jugadores de la tabla una sola vez, con su nombre normalizado,
    # en vez de comparar con ILIKE en cada UPDATE (más rápido y más confiable).
    cur.execute('SELECT DISTINCT game_id, player FROM jugadores_stats;')
    jugadores_db = {}  # (game_id, nombre_normalizado) -> nombre_real_en_db
    for game_id, player in cur.fetchall():
        jugadores_db[(game_id, normalizar(player))] = player

    actualizados, sin_cruce, sin_jugador = 0, 0, 0

    for p in finalizados:
        home_es, away_es = p["home"], p["away"]
        home_en = EQUIPOS_MAP.get(home_es)
        away_en = EQUIPOS_MAP.get(away_es)
        if not home_en or not away_en:
            print(f"  Equipo sin mapear: {home_es} vs {away_es}")
            sin_cruce += 1
            continue

        cur.execute("""
            SELECT game_id FROM calendario_mundial
            WHERE game_id IS NOT NULL AND (
                (home_team ILIKE %s AND away_team ILIKE %s)
                OR (home_team ILIKE %s AND away_team ILIKE %s)
            )
            LIMIT 1
        """, (home_en, away_en, away_en, home_en))
        row = cur.fetchone()
        if not row or not row[0]:
            print(f"  Sin cruce en calendario: {home_en} vs {away_en}")
            sin_cruce += 1
            continue
        game_id = row[0]

        data = obtener_partido_completo(p["id"])
        time.sleep(0.8)
        if data is None:
            continue

        goles, asistencias = {}, {}
        for e in data.get("events", []):
            if e["type"] not in ("goal", "goal-penalty"):
                continue
            equipo = home_en if e["team"] == "home" else away_en
            jugador = e["playerNameFull"]
            goles[(jugador, equipo)] = goles.get((jugador, equipo), 0) + 1
            if e.get("assistFull"):
                asist = e["assistFull"]
                asistencias[(asist, equipo)] = asistencias.get((asist, equipo), 0) + 1

        jugadores = set(goles) | set(asistencias)
        for (jugador, equipo) in jugadores:
            g = goles.get((jugador, equipo), 0)
            a = asistencias.get((jugador, equipo), 0)
            clave = (game_id, normalizar(jugador))
            nombre_real = jugadores_db.get(clave)
            if not nombre_real:
                nombre_real, score = buscar_jugador_similar(jugador, game_id, jugadores_db)
                if nombre_real:
                    print(f"  Match difuso: '{jugador}' -> '{nombre_real}' (score {score:.2f})")
                else:
                    print(f"  Jugador no encontrado en DB: {jugador} ({game_id})")
                    sin_jugador += 1
                    continue
            cur.execute("""
                UPDATE jugadores_stats
                SET goles = %s, asistencias = %s
                WHERE game_id = %s AND player = %s
            """, (g, a, game_id, nombre_real))
            actualizados += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nListo. Filas actualizadas: {actualizados}")
    print(f"Equipos/partidos sin cruce: {sin_cruce}")
    print(f"Jugadores sin cruce de nombre: {sin_jugador}")

if __name__ == "__main__":
    main()
