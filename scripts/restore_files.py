#!/usr/bin/env python3
"""Restauracion de los volumenes con material personal de hefesto-tareas (Vikunja + PostgreSQL de Supabase).

El volumen viaja cifrado con age: la clave privada (AGE_IDENTITY_FILE) es un
insumo externo, no se genera aqui. Exige destino vacio.
"""
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from respaldo_contrato import (RespaldoError, auditar, descifrar_con_age, ejecutar,
                               ejecutar_check, escribir_informe, opciones_restore)

SOFTWARE = "hefesto-tareas"
VERSION = "2.7.0"
DATABASE = "postgresql"
RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ)
os.umask(0o077)
PROHIBIDOS = ["files.tar.gz"]
VOLUMENES = [
    {
        "nombre": "files",
        "artefacto": "files.tar.gz",
        "ruta": "/files"
    }
]


def dc(*args, **kw):
    return subprocess.run(["docker", "compose", *args], check=True, **kw)


def main():
    modo, origen = opciones_restore(sys.argv[1:])
    origen = Path(origen).resolve()
    ejecutar_check(str(origen), SOFTWARE, VERSION, DATABASE, prohibidos=PROHIBIDOS)
    if modo == "dry-run":
        print("Simulacion: el respaldo es integro y no se escribio nada.")
        print("Para restaurar de verdad: --confirmar CONFIRMAR_RESTAURACION")
        return 0
    if dc("ps", "--status", "running", "-q", "app",
          capture_output=True, text=True).stdout.strip():
        raise RespaldoError("app esta activa en el destino; detenerla antes de restaurar", 5)
    if not (RAIZ / ".env").is_file():
        raise RespaldoError("Preparar el .env del destino: no viaja en el respaldo", 5)
    for vol in VOLUMENES:
        encontrado = dc("run", "--rm", "--no-deps", "-T", "--entrypoint", "find",
                        "filetools", vol["ruta"], "-mindepth", "1", "-maxdepth", "1",
                        capture_output=True, text=True).stdout.strip()
        if encontrado:
            raise RespaldoError("El volumen " + vol["nombre"] +
                                " del destino no esta vacio; usar destino nuevo", 5)
    for vol in VOLUMENES:
        cifrado = origen / (vol["artefacto"] + ".age")
        if not cifrado.is_file():
            raise RespaldoError("El respaldo no trae " + vol["artefacto"] +
                                " cifrado: hace falta el receptor age", 5)
        with tempfile.TemporaryDirectory(prefix="hefesto-restore-") as d:
            plano = Path(d) / vol["artefacto"]
            descifrar_con_age(cifrado, plano)
            with tarfile.open(plano) as tf:
                for member in tf:
                    ruta = PurePosixPath(member.name)
                    if (ruta.is_absolute() or ".." in ruta.parts
                            or not (member.isfile() or member.isdir())):
                        raise RespaldoError("Ruta o tipo no admitido: " + member.name, 5)
            with plano.open("rb") as f:
                argumentos = ["run", "--rm", "--no-deps", "-T"]
                if True:
                    argumentos += ["--user", "0"]
                argumentos += ["--entrypoint", "tar", "filetools", "-xzf", "-",
                               "-C", vol["ruta"]]
                dc(*argumentos, stdin=f)
    dc("run", "--rm", "--no-deps", "permissions")

    escribir_informe(origen, software=SOFTWARE, version=VERSION, database=DATABASE,
                     modo="confirmado", resultado="volumenes-restaurados", destino=str(RAIZ))
    auditar(RAIZ, operacion="restore", kit=SOFTWARE, origen=str(origen), destino=str(RAIZ),
            resultado="volumenes-restaurados")
    print("Volumenes restaurados y propietario ajustado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar(main))
