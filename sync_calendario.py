"""
Trae el fixture completo desde elnine.com.ar y actualiza/inserta partidos
faltantes en calendario_mundial (especialmente cuartos en adelante).
"""
import os
import time
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

STAGE_MAP = {
    "group": "Group stage", "round32": "Round of 32", "round16": "Round of 16",
    "quarterfinal": "Quarterfinal", "semifinal": "Semifinal",
    "thirdplace": "3rd place", "final": "Final",
}

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
        {"home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
         "homeScore": m.get("homeScore"), "awayScore": m.get("awayScore"),
         "status": m.get("status"), "stage": m.get("stage"), "date": fecha_str}
        for m in data.get("matches", [])
        if m.get("tournamentCalendarSlug") == "fifa-world-cup"
    ]

def main():
    print("Descargando fixture completo...")
    fechas = pd.date_range("2026-06-11", pd.Timestamp.today()).strftime("%Y-%m-%d").tolist()
    partidos = []
    for f in fechas:
        partidos.extend(obtener_partidos_fecha(f))
        time.sleep(0.8)

    finalizados = [p for p in partidos if p["status"] == "finished"]
    print(f"{len(finalizados)} partidos finalizados en el fixture de elnine.\n")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()

    faltantes = []
    for p in finalizados:
        home = EQUIPOS_MAP.get(p["home"])
        away = EQUIPOS_MAP.get(p["away"])
        if not home or not away:
            continue
        cur.execute("""
            SELECT game_id FROM calendario_mundial
            WHERE (home_team ILIKE %s AND away_team ILIKE %s)
               OR (home_team ILIKE %s AND away_team ILIKE %s)
        """, (home, away, away, home))
        if cur.fetchone() is None:
            faltantes.append((p, home, away))

    print(f"Partidos que faltan en calendario_mundial: {len(faltantes)}\n")
    for p, home, away in faltantes:
        stage = STAGE_MAP.get(p["stage"], p["stage"])
        score = f"{p['homeScore']}–{p['awayScore']}"
        game_id = f"elnine_{p['home']}_{p['away']}_{p['date']}"[:50].replace(" ", "_")
        cur.execute("""
            INSERT INTO calendario_mundial
                (league, season, round, date, home_team, score, away_team, game_id)
            VALUES ('FIFA World Cup', '2026', %s, %s, %s, %s, %s, %s)
        """, (stage, p["date"], home, score, away, game_id))
        print(f"  + Insertado: {home} {score} {away} ({stage})")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nListo. {len(faltantes)} partidos insertados.")

if __name__ == "__main__":
    main()
