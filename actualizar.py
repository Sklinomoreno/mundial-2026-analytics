"""
Actualiza todo el pipeline de datos y levanta la API + Streamlit.
Uso: python actualizar.py
"""
import subprocess
import sys
import time
import os

PROYECTO_DIR = os.path.dirname(os.path.abspath(__file__))

def correr_script(nombre_script):
    print(f"\n{'='*60}")
    print(f"Corriendo: {nombre_script}")
    print(f"{'='*60}\n")
    resultado = subprocess.run(
        [sys.executable, nombre_script],
        cwd=PROYECTO_DIR,
    )
    if resultado.returncode != 0:
        print(f"\n⚠️  {nombre_script} terminó con error (código {resultado.returncode}).")
        respuesta = input("¿Continuar con el resto de todas formas? (s/n): ")
        if respuesta.lower() != "s":
            sys.exit(1)

def main():
    print("Actualizando calendario, jugadores faltantes y goleadores...\n")

    correr_script("cerrar_partidos_pendientes.py")
    correr_script("sync_calendario.py")
    correr_script("sync_partidos_faltantes.py")
    correr_script("sync_goleadores.py")

    print(f"\n{'='*60}")
    print("Sincronización de datos completa.")
    print(f"{'='*60}\n")

    # Mata cualquier instancia previa de FastAPI en el puerto 8000 (evita "Address already in use")
    subprocess.run("lsof -ti:8000 | xargs -r kill -9", shell=True)
    time.sleep(1)

    print("Levantando FastAPI en segundo plano (puerto 8000)...")
    fastapi_proc = subprocess.Popen(
        ["fastapi", "dev", "app/main.py"],
        cwd=PROYECTO_DIR,
        stdout=open(os.path.join(PROYECTO_DIR, "fastapi.log"), "w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(3)

    print("Levantando Streamlit en segundo plano (puerto 8501)...")
    streamlit_proc = subprocess.Popen(
        ["streamlit", "run", "streamlit_app.py", "--server.headless", "true"],
        cwd=PROYECTO_DIR,
        stdout=open(os.path.join(PROYECTO_DIR, "streamlit.log"), "w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(3)

    with open(os.path.join(PROYECTO_DIR, ".pids"), "w") as f:
        f.write(f"{fastapi_proc.pid}\n{streamlit_proc.pid}\n")

    print(f"\n{'='*60}")
    print("Todo listo, mi bro:")
    print("  API:       http://localhost:8000/docs")
    print("  Streamlit: http://localhost:8501")
    print(f"{'='*60}")
    print("\nLogs en fastapi.log y streamlit.log si algo falla.")
    print("Para detener ambos servicios: python detener.py")

if __name__ == "__main__":
    main()
