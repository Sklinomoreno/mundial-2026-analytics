# Mundial 2026 — Panel de Datos y Predicciones

Pipeline completo de analítica deportiva para el Mundial 2026: sincronización automática de datos en vivo, modelo de predicción Poisson, y dashboard público con estadísticas, bracket del torneo y análisis en tiempo real.

**App en vivo:** [mundial-2026-analytics.streamlit.app](https://mundial-2026-analytics-ccn8ka2ktpdkn2dquzbhoj.streamlit.app/)

---

## Arquitectura
elnine.com.ar API  →  PostgreSQL (Railway)  →  FastAPI (Railway)  →  Streamlit (Streamlit Cloud)
↑
Cron Job cada 10 min
(cierra partidos, actualiza goleadores)

| Componente | Tecnología | Dónde vive |
|---|---|---|
| Base de datos | PostgreSQL | Railway |
| API | FastAPI + SQLAlchemy | Railway |
| Sincronización automática | Python (Cron Job) | Railway |
| Frontend | Streamlit + streamlit-echarts | Streamlit Community Cloud |
| Modelo de predicción | Poisson con shrinkage, calibración walk-forward | Jupyter Notebook (local) |

## Funcionalidades

### Stats
- Top goleadores, asistidores, tarjetas amarillas/rojas — con actualización en vivo durante partidos en curso
- KPIs generales del torneo (partidos jugados, goles totales, promedio por partido)
- Gráficos analíticos: barra de goles por equipo, donut de goles por ronda, scatter de eficiencia de tiro
- Comparativa de los equipos en cuartos de final (barra + radar de perfil)

### Bracket
- Cuadro del torneo desde octavos de final, con banderas reales
- Orden por linaje real: detecta automáticamente de qué partido anterior avanzó cada equipo
- Resalta en vivo el partido que se esté jugando

### Predicciones
- Modelo Poisson con shrinkage, ajuste por ranking FIFA, altitud, calor y perfil de árbitro
- Mapa de calor de marcadores posibles, top 5 marcadores más probables
- Mercados adicionales: remates, corners, tarjetas, faltas (Over/Under)
- Recalibración walk-forward: valida el modelo contra resultados reales sin ver el futuro (evita overfitting)

### En vivo
- Proyección minuto a minuto de goles, remates, corners y tarjetas, combinando lo observado con la expectativa pre-partido
- Auto-refresco cada 30 segundos

## Pipeline de datos

1. **`sync_calendario.py`** — trae partidos nuevos finalizados desde elnine.com.ar
2. **`cerrar_partidos_pendientes.py`** — detecta partidos programados que ya terminaron y les asigna resultado real
3. **`sync_partidos_faltantes.py`** — completa estadísticas de jugadores para partidos sin datos
4. **`sync_goleadores.py`** — actualiza goles/asistencias, **incremental** (solo procesa partidos nuevos, no repite trabajo ya hecho)
5. **`sync_todo.py`** — orquesta los 4 anteriores; corre como Cron Job en Railway cada 10 minutos

Para correr todo manualmente en local:

```bash
python actualizar.py
```

## Modelo de predicción (notebook)

El notebook `Mundial.ipynb` contiene el motor de predicción completo:

- Goles esperados vía distribución de Poisson con *shrinkage* hacia la media del torneo
- Ajustes: ranking FIFA, altitud del estadio, calor, perfil de tarjetas del árbitro
- **Calibración walk-forward**: en vez de validar con los mismos partidos usados para entrenar, recorre el torneo en orden cronológico, prediciendo cada partido usando solo información disponible *antes* de que se jugara — evita el sobreajuste de validar con pocos datos
- Chequeo de sensatez automático: alerta si alguna predicción supera un umbral de probabilidad poco realista

Para la siguiente ronda del torneo, solo hace falta editar 3 variables en el notebook (`ROUND_ACTUAL`, `CRUCES_RONDA_ACTUAL`, `PARTIDOS_RONDA_ANTERIOR`) y correr todas las celdas.

## Stack técnico

- **Backend:** FastAPI, SQLAlchemy, psycopg2
- **Frontend:** Streamlit, streamlit-echarts, pandas, matplotlib
- **Modelo:** NumPy, SciPy (Poisson, distribuciones)
- **Datos:** elnine.com.ar (API no oficial)
- **Infraestructura:** Railway (PostgreSQL + API + Cron), Streamlit Community Cloud, GitHub

## Correr en local

```bash
git clone https://github.com/Sklinomoreno/mundial-2026-analytics.git
cd mundial-2026-analytics
pip install -r requirements.txt
```

Crea un archivo `.env` con tus credenciales de PostgreSQL:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mi_proyecto
DB_USER=tu_usuario
DB_PASSWORD=tu_password

Levanta la API y el frontend:

```bash
fastapi dev app/main.py
streamlit run streamlit_app.py
```

## Autor

**Smith Eusebio Lino Moreno**
Bachiller en Ingeniería Industrial (UNI) · Especialista en Business Intelligence y Data Analytics

[LinkedIn](https://www.linkedin.com/in/slino-moreno/)

## Licencia

Proyecto personal con fines de aprendizaje y portafolio. Los datos provienen de una API pública no oficial (elnine.com.ar); este proyecto no está afiliado a la FIFA ni a elnine.com.ar.
