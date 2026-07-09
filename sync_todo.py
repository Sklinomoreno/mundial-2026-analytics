"""
Corre toda la sincronizacion en orden, pensado para correr como Cron Job en Railway
(no lanza FastAPI ni Streamlit, eso ya corre aparte como servicios propios).
"""
import subprocess
import sys

def correr(nombre_script):
    print(f"\n{'='*50}\nCorriendo: {nombre_script}\n{'='*50}")
    resultado = subprocess.run([sys.executable, nombre_script])
    if resultado.returncode != 0:
        print(f"AVISO: {nombre_script} termino con codigo {resultado.returncode}, continuando de todas formas.")

def main():
    correr("cerrar_partidos_pendientes.py")
    correr("sync_calendario.py")
    correr("sync_partidos_faltantes.py")
    correr("sync_goleadores.py")
    print("\nSincronizacion completa.")

if __name__ == "__main__":
    main()
