#!/usr/bin/env python3
"""Restauracion de la base de hefesto-tareas (Vikunja + PostgreSQL de Supabase) en un destino nuevo y vacio.

Sin --confirmar CONFIRMAR_RESTAURACION no se escribe nada; con --dry-run se
simula. El volumen con material personal se restaura aparte (restore_files.py)
y necesita la clave privada age del receptor: es un insumo externo.

El preflight completo (dump presente y descifrable, destino vacio) se ejecuta
ANTES de restaurar: un preflight que falla no deja el esquema a medias.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from respaldo_contrato import (RespaldoError, auditoria_restore, descifrar_con_age, ejecutar,
                               ejecutar_check, escribir_informe, opciones_restore)

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
        print("Simulacion: el respaldo es integro y no se escribio nada.")
        print("Para restaurar de verdad: --confirmar CONFIRMAR_RESTAURACION")
        return 0
    with auditoria_restore(RAIZ, origen, manifiesto):
        return restaurar(origen)


def restaurar(origen):
    dump_cifrado = origen / "public.dump.age"
    if not dump_cifrado.is_file():
        raise RespaldoError("El respaldo no trae public.dump.age; no se restaura", 5)
    # Preflight completo antes de cualquier mutacion: el dump se descifra en
    # un directorio temporal privado (nunca en el respaldo) y se comprueba el
    # destino antes de tocar el esquema.
    with tempfile.TemporaryDirectory(prefix="hefesto-restore-dump-") as dd, \
            tempfile.TemporaryDirectory(prefix="hefesto-restore-list-") as dl:
        dump = Path(dd) / "public.dump"
        descifrar_con_age(dump_cifrado, dump)
        if dc("ps", "--status", "running", "-q", "app",
              capture_output=True, text=True).stdout.strip():
            raise RespaldoError("app esta activa en el destino; detenerla antes de restaurar", 5)
        if not (RAIZ / ".env").is_file():
            raise RespaldoError("Preparar el .env del destino: no viaja en el respaldo", 5)
        count = dc("run", "--rm", "--no-deps", "-T", "--entrypoint", "psql", "dbtools", "-Atc",
                   "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
                   capture_output=True, text=True).stdout.strip()
        if count != "0":
            raise RespaldoError("El esquema public del destino no esta vacio; no se sobrescribe", 5)
        with dump.open("rb") as stream:
            toc = dc("run", "--rm", "--no-deps", "-T", "--entrypoint", "pg_restore", "dbtools",
                     "--list", stdin=stream, stdout=subprocess.PIPE).stdout.decode()
        # public ya existe en Supabase: no se dropea ni se restaura su entrada SCHEMA.
        lines = [line for line in toc.splitlines()
                 if not re.match(r"^\d+;\s+\d+\s+\d+\s+SCHEMA\s+-\s+public(?:\s|$)", line)]
        lista = Path(dl) / "restore.list"
        lista.write_text("\n".join(lines) + "\n")
        os.chmod(dl, 0o755)
        os.chmod(lista, 0o644)
        with dump.open("rb") as stream:
            dc("run", "--rm", "--no-deps", "-T", "-v", dl + ":/restore:ro", "--entrypoint",
               "pg_restore", "dbtools", "--exit-on-error", "--no-owner", "--no-acl",
               "--use-list=/restore/restore.list", "--dbname=postgres", stdin=stream)
    escribir_informe(origen, software=SOFTWARE, version=VERSION, database=DATABASE,
                     modo="confirmado", resultado="base-restaurada", destino=str(RAIZ))
    print("Base restaurada. Restaure los archivos antes de iniciar la aplicacion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar(main))
