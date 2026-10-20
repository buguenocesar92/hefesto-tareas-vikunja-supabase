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
# Los volumenes con material personal solo viajan cifrados con age: su version
# en claro jamas puede estar dentro del respaldo.
PROHIBIDOS = ["files.tar.gz"]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3 scripts/check_backup.py /ruta/respaldo")
    ejecutar_check(sys.argv[1], SOFTWARE, VERSION, DATABASE, prohibidos=PROHIBIDOS,
                   requeridos=("public.dump", "env.vars"))
    print("Manifiesto, checksums y ausencia de secretos en claro verificados.")
    print("No demuestra la recuperacion de la base ni de los volumenes: "
          "hace falta la clave age del receptor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar(main))
