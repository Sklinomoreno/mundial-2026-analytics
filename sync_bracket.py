"""
Avanza ganadores en el bracket: revisa partidos terminados en calendario_mundial
y actualiza la fila de la siguiente ronda (bracket_slots) con el equipo ganador.
Uso: python sync_bracket.py
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)


def parsear_ganador(score, home_team, away_team):
    """Devuelve el nombre del equipo ganador a partir del score, o None si no ha terminado o hay empate."""
    if not score or score.strip() == "":
        return None

    score_limpio = score.replace("–", "-").strip()
    partes = score_limpio.split("-")
    if len(partes) != 2:
        return None

    try:
        goles_home = int(partes[0].strip())
        goles_away = int(partes[1].strip())
    except ValueError:
        return None

    if goles_home > goles_away:
        return home_team
    elif goles_away > goles_home:
        return away_team
    else:
        return None


def avanzar_ganadores():
    with engine.begin() as conn:
        slots = conn.execute(text("""
            SELECT bs.id AS slot_id, bs.feeds_into_slot, bs.home_source_slot, bs.away_source_slot,
                   cm.home_team, cm.away_team, cm.score
            FROM bracket_slots bs
            JOIN calendario_mundial cm ON cm.id = bs.match_id
            WHERE bs.feeds_into_slot IS NOT NULL
        """)).fetchall()

        actualizados = 0

        for slot in slots:
            ganador = parsear_ganador(slot.score, slot.home_team, slot.away_team)
            if ganador is None:
                continue

            destino = conn.execute(text("""
                SELECT bs.id, bs.home_source_slot, bs.away_source_slot, bs.match_id
                FROM bracket_slots bs
                WHERE bs.id = :feeds_into
            """), {"feeds_into": slot.feeds_into_slot}).fetchone()

            if destino is None:
                continue

            if destino.home_source_slot == slot.slot_id:
                campo = "home_team"
            elif destino.away_source_slot == slot.slot_id:
                campo = "away_team"
            else:
                continue

            resultado = conn.execute(text(f"""
                UPDATE calendario_mundial
                SET {campo} = :ganador
                WHERE id = :match_id AND {campo} = 'TBD'
            """), {"ganador": ganador, "match_id": destino.match_id})

            if resultado.rowcount > 0:
                actualizados += 1
                print(f"  → {ganador} avanza a slot {destino.id} ({campo})")

        print(f"\nTotal actualizaciones: {actualizados}")


if __name__ == "__main__":
    print("Revisando partidos terminados para avanzar el bracket...")
    avanzar_ganadores()
    print("Listo.")
