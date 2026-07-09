from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class PartidoResponse(BaseModel):
    game_id: str
    league: Optional[str] = None
    season: Optional[str] = None
    round: Optional[str] = None
    date: Optional[datetime] = None
    time: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    score: Optional[str] = None
    venue: Optional[str] = None
    referee: Optional[str] = None
    attendance: Optional[int] = None

    class Config:
        from_attributes = True

class JugadorStatsResponse(BaseModel):
    game_id: str
    team: Optional[str] = None
    player: Optional[str] = None
    pos: Optional[str] = None
    age: Optional[str] = None
    min: Optional[int] = None
    goles: Optional[int] = None
    asistencias: Optional[int] = None
    tiros: Optional[int] = None
    tiros_arco: Optional[int] = None
    tarjetas_amarillas: Optional[int] = None
    tarjetas_rojas: Optional[int] = None

    class Config:
        from_attributes = True

class JugadorResponse(BaseModel):
    id: int
    nombre: str
    equipo: Optional[str] = None
    goles: Optional[int] = None
    partido: Optional[str] = None

    class Config:
        from_attributes = True

class PrediccionResponse(BaseModel):
    home_team: str
    away_team: str
    round: Optional[str] = None
    prob_local: Optional[float] = None
    prob_empate: Optional[float] = None
    prob_visitante: Optional[float] = None
    over25: Optional[float] = None
    btts: Optional[float] = None
    lambda_tarjetas: Optional[float] = None
    lambda_faltas: Optional[float] = None
    detalle: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class Config:
        from_attributes = True
