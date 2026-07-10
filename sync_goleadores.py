"""
Version incremental: solo procesa partidos NUEVOS (goles_sincronizados = FALSE),
usando directamente el game_id guardado (que es el match_id real de elnine).
Ya no re-descarga ni re-procesa los partidos que ya estan al dia.
"""
import os
import time
import unicodedata
import difflib
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

HEADERS_ELNINE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://elnine.com.ar",
}

def normalizar(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

def buscar_jugador_similar(nombre_buscado, jugadores_db, umbral=0.75):
    nombre_norm = normalizar(nombre_buscado)
    palabras_buscado = nombre_norm.split()

    mejor_score, mejor_nombre = 0, None
    for nombre_db_norm, nombre_real in jugadores_db.items():
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

def obtener_partido_completo(match_id):
    url = f"https://api.elnine.com.ar/match/{match_id}"
    headers = {**HEADERS_ELNINE, "Referer": f"https://elnine.com.ar/partido/{match_id}"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()["matchDetail"]

def main():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT game_id, home_team, away_team FROM calendario_mundial
        WHERE score IS NOT NULL AND score != ''
          AND game_id IS NOT NULL AND game_id != ''
          AND (goles_sincronizados IS NULL OR goles_sincronizados = FALSE)
    """)
    pendientes = cur.fetchall()
    print(f"Partidos pendientes de sincronizar goles: {len(pendientes)}")

    if not pendientes:
        print("Nada que hacer, todo esta al dia.")
        cur.close(); conn.close()
        return

    actualizados_total = 0

    for game_id, home_en, away_en in pendientes:
        print(f"Procesando: {home_en} vs {away_en} ({game_id})")
        try:
            data = obtener_partido_completo(game_id)
        except Exception as e:
            print(f"  Error descargando: {e}")
            continue
        time.sleep(0.5)

        cur.execute('SELECT player FROM jugadores_stats WHERE game_id = %s;', (game_id,))
        jugadores_db = {normalizar(r[0]): r[0] for r in cur.fetchall()}

        goles, asistencias = {}, {}
        for e in data.get("events", []):
            if e["type"] not in ("goal", "goal-penalty"):
                continue
            equipo = home_en if e["team"] == "home" else away_en
            goles[(e["playerNameFull"], equipo)] = goles.get((e["playerNameFull"], equipo), 0) + 1
            if e.get("assistFull"):
                asistencias[(e["assistFull"], equipo)] = asistencias.get((e["assistFull"], equipo), 0) + 1

        actualizados_partido = 0
        jugadores_partido = set(goles) | set(asistencias)
        for (jugador, equipo) in jugadores_partido:
            g = goles.get((jugador, equipo), 0)
            a = asistencias.get((jugador, equipo), 0)
            nombre_real = jugadores_db.get(normalizar(jugador))
            if not nombre_real:
                nombre_real, score = buscar_jugador_similar(jugador, jugadores_db)
                if nombre_real:
                    print(f"  Match difuso: '{jugador}' -> '{nombre_real}' ({score:.2f})")
                else:
                    print(f"  Jugador no encontrado: {jugador}")
                    continue
            cur.execute("""
                UPDATE jugadores_stats SET goles = %s, asistencias = %s
                WHERE game_id = %s AND player = %s
            """, (g, a, game_id, nombre_real))
            actualizados_partido += cur.rowcount

        cur.execute("UPDATE calendario_mundial SET goles_sincronizados = TRUE WHERE game_id = %s", (game_id,))
        conn.commit()
        print(f"  {actualizados_partido} filas actualizadas. Marcado como sincronizado.")
        actualizados_total += actualizados_partido

    cur.close()
    conn.close()
    print(f"\nListo. Total filas actualizadas: {actualizados_total}")

if __name__ == "__main__":
    main()
