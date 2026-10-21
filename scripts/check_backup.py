#!/usr/bin/env python3
"""Verificacion de integridad de un respaldo de hefesto-tareas.

Codigos de salida: 0 integro, 1 uso, 2 integridad o manifiesto invalido,
4 material sensible en claro dentro del respaldo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from respaldo_contrato import ejecutar, ejecutar_check

SOFTWARE = "hefesto-tareas"
VERSION = "2.7.0"
DATABASE = "postgresql"
# El dump y el volumen con material personal solo viajan cifrados con age: su
# version en claro jamas puede estar dentro del respaldo.
PROHIBIDOS = ["files.tar.gz", "public.dump"]
# Artefactos que produce el kit: cada uno viaja en el manifiesto o su
# exclusion esta declarada en "excluidos".
ESPERADOS = ("env.vars", "public.dump.age", "files.tar.gz.age")
# Artefactos que solo faltan si el manifiesto declara su exclusion.
EXCLUIBLES = {"dump": "public.dump.age", "files": "files.tar.gz.age"}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3 scripts/check_backup.py /ruta/respaldo")
    manifiesto = ejecutar_check(sys.argv[1], SOFTWARE, VERSION, DATABASE,
                                esperados=ESPERADOS, prohibidos=PROHIBIDOS,
                                requeridos=("env.vars",), excluibles=EXCLUIBLES)
    print("Manifiesto, checksums y ausencia de secretos en claro verificados.")
    if manifiesto.get("excluidos"):
        print("ATENCION: el respaldo declara excluidos: "
              + ", ".join(manifiesto["excluidos"])
              + ". Sin receptor age no hay copia cifrada de esos datos.")
    print("No demuestra la recuperacion de la base ni de los volumenes: "
          "hace falta la clave age del receptor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar(main))
