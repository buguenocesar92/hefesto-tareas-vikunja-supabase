#!/usr/bin/env python3
"""Restauracion de los volumenes con material personal de hefesto-tareas (Vikunja + PostgreSQL de Supabase).

El volumen viaja cifrado con age: la clave privada (AGE_IDENTITY_FILE) es un
insumo externo, no se genera aqui. Exige destino vacio.

El preflight completo (volumen presente, descifrado, tar valido, destino
vacio) se ejecuta ANTES de extraer nada.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from respaldo_contrato import (RespaldoError, auditoria_restore, descifrar_con_age, ejecutar,
                               ejecutar_check, escribir_informe, opciones_restore, validar_tar)

SOFTWARE = "hefesto-tareas"
VERSION = "2.7.0"
DATABASE = "postgresql"
RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ)
os.umask(0o077)
PROHIBIDOS = ["files.tar.gz", "public.dump"]
ESPERADOS = ("env.vars", "public.dump.age", "files.tar.gz.age")
EXCLUIBLES = {"dump": "public.dump.age", "files": "files.tar.gz.age"}


def dc(*args, **kw):
    return subprocess.run(["docker", "compose", *args], check=True, **kw)


def main():
    modo, origen = opciones_restore(sys.argv[1:])
    origen = Path(origen).resolve()
    manifiesto = ejecutar_check(str(origen), SOFTWARE, VERSION, DATABASE,
                                esperados=ESPERADOS, prohibidos=PROHIBIDOS,
                                requeridos=("env.vars",), excluibles=EXCLUIBLES)
    if modo == "dry-run":
        print("Simulacion: checksums integros; no demuestra descifrado ni recuperacion.")
        return 0
    with auditoria_restore(RAIZ, origen, manifiesto):
        return restaurar(origen)


def restaurar(origen):
    cifrado = origen / "files.tar.gz.age"
    if not cifrado.is_file():
        raise RespaldoError("El respaldo no trae files.tar.gz.age; no se restaura", 5)
    with tempfile.TemporaryDirectory(prefix="hefesto-restore-") as d:
        plano = Path(d) / "files.tar.gz"
        descifrar_con_age(cifrado, plano)
        validar_tar(plano)
        if dc("ps", "--status", "running", "-q", "app",
              capture_output=True, text=True).stdout.strip():
            raise RespaldoError("app esta activa en el destino; detenerla antes de restaurar", 5)
        if not (RAIZ / ".env").is_file():
            raise RespaldoError("Preparar el .env del destino: no viaja en el respaldo", 5)
        encontrado = dc("run", "--rm", "--no-deps", "-T", "--entrypoint", "find",
                        "filetools", "/files", "-mindepth", "1", "-maxdepth", "1",
                        capture_output=True, text=True).stdout.strip()
        if encontrado:
            raise RespaldoError("El volumen files del destino no esta vacio", 5)
        with plano.open("rb") as f:
            dc("run", "--rm", "--no-deps", "-T", "--user", "0", "--entrypoint", "tar",
               "filetools", "-xzf", "-", "-C", "/files", stdin=f)
    dc("run", "--rm", "--no-deps", "permissions")
    escribir_informe(origen, software=SOFTWARE, version=VERSION, database=DATABASE,
                     modo="confirmado", resultado="volumenes-restaurados", destino=str(RAIZ))
    print("Volumenes restaurados y propietario ajustado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar(main))
