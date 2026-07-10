from sqlalchemy import text
from sqlalchemy.orm import Session

def get_partidos_proximos(db: Session, limit: int = 10):
    query = text("""
        SELECT game_id, league, season, round, date, time,
               home_team, away_team, score, venue, referee, attendance
        FROM calendario_mundial
        WHERE date >= CURRENT_DATE
        ORDER BY date ASC
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_partido_by_id(db: Session, game_id: str):
    query = text("""
        SELECT game_id, league, season, round, date, time,
               home_team, away_team, score, venue, referee, attendance
        FROM calendario_mundial
        WHERE game_id = :game_id
    """)
    return db.execute(query, {"game_id": game_id}).mappings().first()

def get_partidos_por_equipo(db: Session, equipo: str, limit: int = 10):
    query = text("""
        SELECT game_id, league, season, round, date, time,
               home_team, away_team, score, venue, referee, attendance
        FROM calendario_mundial
        WHERE home_team ILIKE :equipo OR away_team ILIKE :equipo
        ORDER BY date ASC
        LIMIT :limit
    """)
    return db.execute(query, {"equipo": f"%{equipo}%", "limit": limit}).mappings().all()

def get_stats_by_game(db: Session, game_id: str):
    query = text("""
        SELECT game_id, team, player, pos, age, min,
               goles, asistencias, tiros, tiros_arco,
               tarjetas_amarillas, tarjetas_rojas
        FROM jugadores_stats
        WHERE game_id = :game_id
        ORDER BY goles DESC NULLS LAST
    """)
    return db.execute(query, {"game_id": game_id}).mappings().all()

def get_top_goleadores(db: Session, limit: int = 10):
    query = text("""
        SELECT player, team, SUM(goles) AS total_goles
        FROM jugadores_stats
        WHERE goles IS NOT NULL
        GROUP BY player, team
        ORDER BY total_goles DESC
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_jugadores(db: Session, limit: int = 20):
    query = text("""
        SELECT id, nombre, equipo, goles, partido
        FROM jugadores
        ORDER BY goles DESC NULLS LAST
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_predicciones(db: Session, limit: int = 20, ronda: str = None):
    if ronda:
        query = text("""
            SELECT home_team, away_team, round, prob_local, prob_empate,
                   prob_visitante, over25, btts, lambda_tarjetas, lambda_faltas, detalle
            FROM predicciones
            WHERE round = :ronda
            ORDER BY fecha_prediccion DESC
            LIMIT :limit
        """)
        return db.execute(query, {"limit": limit, "ronda": ronda}).mappings().all()
    query = text("""
        SELECT home_team, away_team, round, prob_local, prob_empate,
               prob_visitante, over25, btts, lambda_tarjetas, lambda_faltas, detalle
        FROM predicciones
        ORDER BY fecha_prediccion DESC
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_partidos_por_ronda(db: Session, ronda: str):
    query = text("""
        SELECT game_id, home_team, away_team, round
        FROM calendario_mundial
        WHERE round = :ronda AND game_id IS NOT NULL AND game_id != ''
        ORDER BY date ASC
    """)
    return db.execute(query, {"ronda": ronda}).mappings().all()


def get_partidos_por_ronda(db: Session, ronda: str):
    query = text("""
        SELECT game_id, home_team, away_team, round
        FROM calendario_mundial
        WHERE round ILIKE :ronda AND game_id IS NOT NULL AND game_id != ''
        ORDER BY date ASC
    """)
    return db.execute(query, {"ronda": ronda}).mappings().all()

def get_top_asistencias(db: Session, limit: int = 10):
    query = text("""
        SELECT player, team, SUM(asistencias) AS total_asistencias
        FROM jugadores_stats
        WHERE asistencias IS NOT NULL
        GROUP BY player, team
        ORDER BY total_asistencias DESC
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_top_tarjetas_amarillas(db: Session, limit: int = 10):
    query = text("""
        SELECT player, team, SUM(tarjetas_amarillas) AS total_amarillas
        FROM jugadores_stats
        WHERE tarjetas_amarillas IS NOT NULL
        GROUP BY player, team
        ORDER BY total_amarillas DESC
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_top_tarjetas_rojas(db: Session, limit: int = 10):
    query = text("""
        SELECT player, team, SUM(tarjetas_rojas) AS total_rojas
        FROM jugadores_stats
        WHERE tarjetas_rojas IS NOT NULL
        GROUP BY player, team
        HAVING SUM(tarjetas_rojas) > 0
        ORDER BY total_rojas DESC
        LIMIT :limit
    """)
    return db.execute(query, {"limit": limit}).mappings().all()

def get_todos_partidos_ronda(db: Session, ronda: str):
    query = text("""
        SELECT home_team, away_team, score, date, game_id
        FROM calendario_mundial
        WHERE round = :ronda
        ORDER BY date ASC
    """)
    return db.execute(query, {"ronda": ronda}).mappings().all()

def get_goles_por_equipo(db: Session):
    query = text("""
        SELECT team, SUM(goles) AS total_goles
        FROM jugadores_stats
        WHERE goles IS NOT NULL
        GROUP BY team
        ORDER BY total_goles DESC
    """)
    return db.execute(query).mappings().all()

def get_kpis_torneo(db: Session):
    query = text("""
        SELECT
            COUNT(*) FILTER (WHERE score IS NOT NULL AND score != '') AS partidos_jugados,
            (SELECT COUNT(DISTINCT player) FROM jugadores_stats WHERE goles > 0) AS goleadores_distintos
        FROM calendario_mundial
    """)
    row = db.execute(query).mappings().first()

    query_goles = text("""
        SELECT SUM(goles) AS total_goles FROM jugadores_stats WHERE goles IS NOT NULL
    """)
    total_goles = db.execute(query_goles).scalar() or 0

    partidos = row["partidos_jugados"] or 1
    return {
        "partidos_jugados": row["partidos_jugados"],
        "total_goles": int(total_goles),
        "promedio_goles_partido": round(total_goles / partidos, 2),
        "goleadores_distintos": row["goleadores_distintos"],
    }
