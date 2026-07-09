"""
Detecta automaticamente partidos finalizados que tienen game_id en calendario_mundial
pero CERO filas en jugadores_stats, y los llena usando elnine.com.ar.
Ya no requiere lista manual de partidos - funciona para cualquier ronda (semis, final, etc).
"""
import os
import time
import unicodedata
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
EQUIPOS_MAP_INV = {v: k for k, v in EQUIPOS_MAP.items()}

POSICION_MAP = {"Arquero": "GK", "Defensor": "DF", "Mediocampista": "MF", "Delantero": "FW"}

def normalizar(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

def obtener_partidos_de_fixture(fecha_str):
    url = f"https://api.elnine.com.ar/schedule?date={fecha_str}"
    headers = {**HEADERS_ELNINE, "Referer": "https://elnine.com.ar/"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
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
        print(f"  Error match {match_id}: {e}")
        return None

def encontrar_partidos_sin_jugadores(cur):
    """Detecta automaticamente partidos finalizados sin ninguna fila en jugadores_stats."""
    cur.execute("""
        SELECT c.game_id, c.home_team, c.away_team, c.round
        FROM calendario_mundial c
        LEFT JOIN jugadores_stats j ON c.game_id = j.game_id
        WHERE c.score IS NOT NULL AND c.score != ''
          AND c.game_id IS NOT NULL AND c.game_id != ''
        GROUP BY c.game_id, c.home_team, c.away_team, c.round
        HAVING COUNT(j.game_id) = 0
    """)
    return cur.fetchall()

def main():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()

    faltantes = encontrar_partidos_sin_jugadores(cur)
    print(f"Partidos detectados sin jugadores cargados: {len(faltantes)}\n")

    if not faltantes:
        print("Nada que hacer, todos los partidos finalizados ya tienen jugadores.")
        cur.close(); conn.close()
        return

    # El game_id en calendario_mundial YA ES el match_id de elnine (asi lo dejamos en sync_calendario.py)
    insertados_total = 0

    for match_id, home_db, away_db, round_actual in faltantes:
        print(f"Procesando: {home_db} vs {away_db} ({round_actual}) - match_id: {match_id}")
        data = obtener_partido_completo(match_id)
        time.sleep(0.8)
        if data is None:
            print("  No se pudo descargar el detalle.\n")
            continue

        goles, asistencias = {}, {}
        for e in data.get("events", []):
            if e["type"] not in ("goal", "goal-penalty"):
                continue
            equipo = home_db if e["team"] == "home" else away_db
            goles[(e["playerNameFull"], equipo)] = goles.get((e["playerNameFull"], equipo), 0) + 1
            if e.get("assistFull"):
                asistencias[(e["assistFull"], equipo)] = asistencias.get((e["assistFull"], equipo), 0) + 1

        tarjetas_amarillas, tarjetas_rojas = {}, {}
        for e in data.get("events", []):
            if e["type"] == "yellow":
                clave = (e["playerNameFull"], home_db if e["team"] == "home" else away_db)
                tarjetas_amarillas[clave] = tarjetas_amarillas.get(clave, 0) + 1
            elif e["type"] == "red":
                clave = (e["playerNameFull"], home_db if e["team"] == "home" else away_db)
                tarjetas_rojas[clave] = tarjetas_rojas.get(clave, 0) + 1

        insertados_partido = 0
        for lado, equipo in [("homeLineup", home_db), ("awayLineup", away_db)]:
            lineup = data.get(lado, {})
            for j in lineup.get("players", []) + lineup.get("subs", []):
                nombre = j["nameFull"]
                s = j.get("stats", {}) or {}
                pos = POSICION_MAP.get(j.get("position"), j.get("position"))
                clave = (nombre, equipo)

                cur.execute("""
                    INSERT INTO jugadores_stats
                        (league, season, game, team, player, jersey_number, pos, age, min,
                         goles, asistencias, tiros, tiros_arco,
                         tarjetas_amarillas, tarjetas_rojas, game_id)
                    VALUES ('FIFA World Cup', '2026', %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id, player) DO NOTHING
                """, (
                    f"{home_db} vs {away_db}", equipo, nombre, j.get("number"), pos, j.get("age"),
                    s.get("minutesPlayed"),
                    goles.get(clave, 0), asistencias.get(clave, 0),
                    s.get("shots"), s.get("shotsOnTarget"),
                    tarjetas_amarillas.get(clave, 0), tarjetas_rojas.get(clave, 0),
                    match_id,
                ))
                insertados_partido += cur.rowcount

        conn.commit()
        print(f"  {insertados_partido} jugadores insertados.\n")
        insertados_total += insertados_partido

    cur.close()
    conn.close()
    print(f"Listo. Total jugadores insertados: {insertados_total}")

if __name__ == "__main__":
    main()
