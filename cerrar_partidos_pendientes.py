"""
Busca partidos pendientes en calendario_mundial (score vacio, con rival real ya definido,
no 'TBD') y, si ya terminaron en elnine, les llena el game_id real y el marcador.
Se debe correr ANTES de sync_partidos_faltantes.py y sync_goleadores.py.
"""
import os
import time
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

HEADERS_ELNINE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://elnine.com.ar",
}

EQUIPOS_MAP_INV = {
    "Algeria": "Argelia", "Argentina": "Argentina", "Australia": "Australia",
    "Austria": "Austria", "Belgium": "Bélgica", "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Brazil": "Brasil", "Cabo Verde": "Islas Cabo Verde", "Canada": "Canadá",
    "Colombia": "Colombia", "Congo DR": "RD Congo", "Croatia": "Croacia",
    "Curaçao": "Curazao", "Czechia": "República Checa", "Côte d'Ivoire": "Costa de Marfil",
    "Ecuador": "Ecuador", "Egypt": "Egipto", "England": "Inglaterra",
    "France": "Francia", "Germany": "Alemania", "Ghana": "Ghana",
    "Haiti": "Haití", "IR Iran": "Irán", "Iraq": "Irak", "Japan": "Japón",
    "Jordan": "Jordania", "Korea Republic": "Corea del Sur", "Mexico": "México",
    "Morocco": "Marruecos", "Netherlands": "Países Bajos", "New Zealand": "Nueva Zelanda",
    "Norway": "Noruega", "Panama": "Panamá", "Paraguay": "Paraguay", "Portugal": "Portugal",
    "Qatar": "Qatar", "Saudi Arabia": "Arabia Saudita", "Scotland": "Escocia",
    "Senegal": "Senegal", "South Africa": "Sudáfrica", "Spain": "España", "Sweden": "Suecia",
    "Switzerland": "Suiza", "Tunisia": "Túnez", "Türkiye": "Turquía",
    "United States": "Estados Unidos", "Uruguay": "Uruguay", "Uzbekistan": "Uzbekistán",
}

def buscar_match_id(home_es, away_es, dias_atras=10):
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
                return m["id"], m.get("status")
        time.sleep(0.3)
    return None, None

def main():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT home_team, away_team, round FROM calendario_mundial
        WHERE (score IS NULL OR score = '')
          AND away_team != 'TBD' AND home_team != 'TBD'
    """)
    pendientes = cur.fetchall()
    print(f"Partidos pendientes encontrados: {len(pendientes)}")

    cerrados = 0
    for home_en, away_en, ronda in pendientes:
        home_es = EQUIPOS_MAP_INV.get(home_en, home_en)
        away_es = EQUIPOS_MAP_INV.get(away_en, away_en)

        match_id, status = buscar_match_id(home_es, away_es)
        if not match_id:
            print(f"  {home_en} vs {away_en} ({ronda}): no encontrado en elnine todavia.")
            continue

        if status != "finished":
            print(f"  {home_en} vs {away_en} ({ronda}): status = {status}, aun no termina.")
            continue

        url = f"https://api.elnine.com.ar/match/{match_id}"
        headers = {**HEADERS_ELNINE, "Referer": f"https://elnine.com.ar/partido/{match_id}"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        detalle = r.json()["matchDetail"]
        gh, ga = detalle["homeTeam"]["score"], detalle["awayTeam"]["score"]
        score_str = f"{gh}-{ga}"

        cur.execute("""
            UPDATE calendario_mundial SET game_id = %s, score = %s
            WHERE home_team = %s AND away_team = %s AND round = %s
        """, (match_id, score_str, home_en, away_en, ronda))
        conn.commit()
        print(f"  Cerrado: {home_en} {score_str} {away_en} ({ronda}) -> game_id {match_id}")
        cerrados += 1
        time.sleep(0.5)

    cur.close()
    conn.close()
    print(f"\nListo. Partidos cerrados: {cerrados}")

if __name__ == "__main__":
    main()
