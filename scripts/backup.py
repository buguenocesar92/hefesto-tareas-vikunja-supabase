#!/usr/bin/env python3
"""Respaldo de hefesto-tareas (Vikunja + PostgreSQL de Supabase).

Reglas de material sensible:
- El .env nunca se copia en claro: solo env.vars y, si hay receptor age, el
  .env cifrado (env.age).
- El dump de la base (cuentas, correos y hashes de contrasena) y el volumen de
  archivos (adjuntos de tareas) son material personal: viajan cifrados con age
  o no viajan, y el manifiesto declara cada exclusion. Los permisos
  restrictivos no son cifrado: no hay dump en claro en disco.
Ver docs/CONTRATO-RESPALDO.md.
"""
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from respaldo_contrato import (RespaldoError, artefactos_presentes, cifrar_con_age,
                               escribir_manifiesto, ejecutar, exportar_env,
                               marcar_fallido, receptor_age)

SOFTWARE = "hefesto-tareas"
VERSION = "2.7.0"
DATABASE = "postgresql"
RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ)
os.umask(0o077)


def dc(*args, **kw):
    return subprocess.run(["docker", "compose", *args], check=True, **kw)


def main():
    if not (RAIZ / ".env").is_file():
        raise RespaldoError("Falta .env: el respaldo necesita el entorno del kit", 5)
    if not dc("ps", "--status", "running", "-q", "app",
              capture_output=True, text=True).stdout.strip():
        raise RespaldoError("app no esta activa en este contexto Compose; "
                            "revisar recurso y proyecto.", 5)
    carpeta = (RAIZ / "backups" /
               datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    carpeta.mkdir(parents=True, mode=0o700)
    meta = {}
    excluidos = []
    try:
        try:
            dc("stop", "app")
            receptor = receptor_age()
            if receptor:
                # El dump va del productor a age: nunca toca el disco en claro.
                cifrar_con_age(
                    lambda flujo: dc("run", "--rm", "--no-deps", "-T", "--entrypoint", "pg_dump",
                                     "dbtools", "--format=custom", "--schema=public",
                                     "--no-owner", "--no-acl", stdout=flujo),
                    carpeta / "public.dump.age", receptor)
                meta["dump"] = "public.dump.age (cifrado con age)"
            else:
                meta["dump"] = ("excluido: el dump contiene cuentas, correos y hashes de "
                                "contrasena y no hay receptor age configurado")
                excluidos.append("dump")

            if receptor:
                cifrar_con_age(
                    lambda flujo: dc("run", "--rm", "--no-deps", "-T", "--entrypoint", "tar",
                                     "filetools", "-czf", "-", "-C", "/files", ".", stdout=flujo),
                    carpeta / "files.tar.gz.age", receptor)
                meta["files"] = "files.tar.gz.age (cifrado con age)"
            else:
                meta["files"] = ("excluido: el volumen de archivos contiene material personal "
                                 "y no hay receptor age configurado")
                excluidos.append("files")

            meta.update(exportar_env(RAIZ, carpeta))
            if (RAIZ / "compose.yaml").is_file():
                shutil.copy2(RAIZ / "compose.yaml", carpeta / "compose.yaml")
        finally:
            dc("start", "app")
        meta["excluidos"] = sorted(excluidos)
        artefactos = artefactos_presentes(carpeta)
        escribir_manifiesto(carpeta, SOFTWARE, VERSION, DATABASE, artefactos, extra=meta)
    except Exception:
        marcar_fallido(carpeta, SOFTWARE, VERSION, DATABASE)
        raise
    print("Respaldo completo:", carpeta)
    if excluidos:
        print("ATENCION: el respaldo NO incluye " + ", ".join(excluidos) +
              ": no es una copia de la base ni de los adjuntos. "
              "Configura AGE_RECIPIENT (o SOPS_AGE_RECIPIENT) para respaldarlos.")
    else:
        print("El .env, el dump y los adjuntos no viajan en claro: todo cifrado con age.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar(main))
