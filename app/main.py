from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from . import crud, models
from .live import obtener_analisis_vivo
from .database import get_db

app = FastAPI(title="Mundial 2026 - API de Datos")

@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API de datos Mundial 2026"}

@app.get("/partidos/proximos", response_model=List[models.PartidoResponse])
def proximos_partidos(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_partidos_proximos(db, limit)

@app.get("/partidos/{game_id}", response_model=models.PartidoResponse)
def partido_por_id(game_id: str, db: Session = Depends(get_db)):
    result = crud.get_partido_by_id(db, game_id)
    if not result:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return result

@app.get("/partidos", response_model=List[models.PartidoResponse])
def partidos_por_equipo(equipo: str = Query(...), limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_partidos_por_equipo(db, equipo, limit)

@app.get("/stats/{game_id}", response_model=List[models.JugadorStatsResponse])
def stats_de_partido(game_id: str, db: Session = Depends(get_db)):
    return crud.get_stats_by_game(db, game_id)

@app.get("/goleadores")
def top_goleadores(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_top_goleadores(db, limit)

@app.get("/jugadores", response_model=List[models.JugadorResponse])
def listar_jugadores(limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_jugadores(db, limit)

@app.get("/predicciones", response_model=List[models.PrediccionResponse])
def listar_predicciones(limit: int = 20, ronda: str = None, db: Session = Depends(get_db)):
    return crud.get_predicciones(db, limit, ronda)

@app.get("/partidos/ronda/{ronda}")
def partidos_por_ronda(ronda: str, db: Session = Depends(get_db)):
    return crud.get_partidos_por_ronda(db, ronda)


@app.get("/live")
def live(home: str, away: str):
    return obtener_analisis_vivo(home, away)


@app.get("/asistencias")
def top_asistencias(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_top_asistencias(db, limit)

@app.get("/tarjetas-amarillas")
def top_tarjetas_amarillas(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_top_tarjetas_amarillas(db, limit)

@app.get("/tarjetas-rojas")
def top_tarjetas_rojas(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_top_tarjetas_rojas(db, limit)

@app.get("/bracket/{ronda}")
def bracket_ronda(ronda: str, db: Session = Depends(get_db)):
    return crud.get_todos_partidos_ronda(db, ronda)
