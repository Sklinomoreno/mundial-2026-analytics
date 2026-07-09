import os
import subprocess

PROYECTO_DIR = os.path.dirname(os.path.abspath(__file__))
pids_file = os.path.join(PROYECTO_DIR, ".pids")

if not os.path.exists(pids_file):
    print("No hay procesos registrados corriendo.")
else:
    with open(pids_file) as f:
        pids = [line.strip() for line in f if line.strip()]
    for pid in pids:
        subprocess.run(["kill", "-9", pid])
        print(f"Detenido proceso {pid}")
    os.remove(pids_file)
    print("Listo, FastAPI y Streamlit detenidos.")
