"""
Monitor en vivo de un partido: se refresca cada minuto y proyecta el total final
(goles, tarjetas, corners, remates) combinando lo que ya paso en el partido con
la expectativa pre-match que guardamos en la tabla predicciones.

Uso: python live_match.py "Francia" "Marruecos"
"""
import sys
import time
import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

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
    """Busca el match_id de elnine probando los ultimos dias (partido de hoy o reciente)."""
    from datetime import timedelta
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
                return m["id"], h, a
    return None, None, None

def obtener_estado_vivo(match_id):
    url = f"https://api.elnine.com.ar/match/{match_id}/stats"
    headers = {**HEADERS_ELNINE, "Referer": f"https://elnine.com.ar/partido/{match_id}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error consultando estado en vivo: {e}")
        return None

def obtener_prediccion_guardada(home_en, away_en):
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
    """, (home_en, away_en, away_en, home_en))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    lambda_tarjetas, lambda_faltas, detalle = row
    lam_goles_pre = 0
    lam_remates_pre = detalle.get("lambda_remates") if detalle else None
    lam_remates_arco_pre = detalle.get("lambda_remates_arco") if detalle else None
    lam_corners_pre = detalle.get("lambda_corners") if detalle else None
    if detalle and detalle.get("grilla_completa"):
        for celda in detalle["grilla_completa"]:
            lam_goles_pre += celda["prob"] * (celda["goles_local"] + celda["goles_visit"])
    return {
        "lam_goles": lam_goles_pre, "lam_remates": lam_remates_pre,
        "lam_remates_arco": lam_remates_arco_pre, "lam_corners": lam_corners_pre,
        "lam_tarjetas": lambda_tarjetas, "lam_faltas": lambda_faltas,
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

def main():
    if len(sys.argv) != 3:
        print("Uso: python live_match.py \"Equipo Local\" \"Equipo Visita\" (en español, como en elnine)")
        sys.exit(1)

    home_es, away_es = sys.argv[1], sys.argv[2]
    home_en = EQUIPOS_MAP.get(home_es, home_es)
    away_en = EQUIPOS_MAP.get(away_es, away_es)

    match_id, home_real, away_real = buscar_match_id_hoy(home_es, away_es)
    if not match_id:
        print(f"No se encontro el partido {home_es} vs {away_es} en los ultimos dias.")
        sys.exit(1)

    pre = obtener_prediccion_guardada(home_en, away_en)
    if pre is None:
        print(f"Aviso: no hay prediccion pre-match guardada para {home_en} vs {away_en}. "
              f"Corre el notebook para este partido antes de usar el monitor en vivo.")

    print(f"Monitoreando: {home_real} vs {away_real} (match_id: {match_id})")
    print("Refrescando cada 60 segundos. Ctrl+C para detener.\n")

    while True:
        estado = obtener_estado_vivo(match_id)
        if estado is None:
            time.sleep(60)
            continue

        stats_dict = {item["label"]: item for item in estado.get("stats", [])}
        minuto = estado.get("minute", 0)

        def val(label, lado):
            item = stats_dict.get(label)
            return item.get(lado, 0) if item else 0

        goles_actuales = val("Goles", "home") + val("Goles", "away") if "Goles" in stats_dict else None
        remates = val("Remates", "home") + val("Remates", "away")
        remates_arco = val("Remates al arco", "home") + val("Remates al arco", "away")
        corners = val("Saques de esquina", "home") + val("Saques de esquina", "away")
        amarillas = val("Tarjetas amarillas", "home") + val("Tarjetas amarillas", "away")
        faltas = val("Faltas", "home") + val("Faltas", "away")

        os.system("clear")
        print(f"=== Minuto {minuto}' === (actualizado {datetime.now().strftime('%H:%M:%S')})\n")
        print(f"{'Metrica':<20} {'Actual':>8} {'Proyeccion final':>18}")
        print("-" * 50)

        if pre:
            filas = [
                ("Remates", remates, pre["lam_remates"]),
                ("Remates al arco", remates_arco, pre["lam_remates_arco"]),
                ("Corners", corners, pre["lam_corners"]),
                ("Tarjetas amarillas", amarillas, pre["lam_tarjetas"]),
                ("Faltas", faltas, pre["lam_faltas"]),
            ]
            for nombre, actual, lam_pre in filas:
                proy = proyectar(actual, minuto, lam_pre)
                proy_str = f"{proy:.1f}" if proy is not None else "N/D"
                print(f"{nombre:<20} {actual:>8} {proy_str:>18}")
        else:
            print("(sin prediccion pre-match para comparar -- solo mostrando datos en vivo)")
            print(f"{'Remates':<20} {remates:>8}")
            print(f"{'Remates al arco':<20} {remates_arco:>8}")
            print(f"{'Corners':<20} {corners:>8}")
            print(f"{'Tarjetas amarillas':<20} {amarillas:>8}")
            print(f"{'Faltas':<20} {faltas:>8}")

        print("\n(Ctrl+C para detener)")
        time.sleep(60)

if __name__ == "__main__":
    main()

