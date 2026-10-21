#!/usr/bin/env python3
"""Contrato comun de respaldo y restauracion (docs/CONTRATO-RESPALDO.md).

Este modulo implementa el contrato normativo del flujo orquestado de Hefesto
Studio. Lo usan backup.py, check_backup.py y restore.py.

Reglas que implementa:
- El .env NUNCA se copia en claro: solo sus nombres (env.vars) y, si hay
  receptor age, el cifrado (env.age). Sin receptor, el respaldo sale sin el
  .env y el manifiesto lo declara. No hay modo degradado a texto plano.
- El dump de la base y el volumen con material personal viajan cifrados con
  age o no viajan: el manifiesto declara cada exclusion en "excluidos".
- manifest.json lleva siempre software, version, database, sha256 y status.
- check_backup devuelve 0 (integro), 1 (uso), 2 (integridad) o 4 (secreto en claro).
- restore exige --confirmar CONFIRMAR_RESTAURACION, valida los sha256 antes de
  escribir, exige destino vacio y deja restore-report.json y auditoria.
"""
from __future__ import annotations

import datetime
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

CLAVES_MANIFIESTO = ("software", "version", "database", "sha256", "status")
CONFIRMACION = "CONFIRMAR_RESTAURACION"
VARS_RECIPIENTE = ("AGE_RECIPIENT", "SOPS_AGE_RECIPIENT")
# Solo se acepta una linea con forma de asignacion: nombre + '='.
ASIGNACION_ENV = re.compile(r"^(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=")
# Un nombre de variable es corto y convencional; un fragmento base64 o PEM no.
NOMBRE_ENV_LARGO = re.compile(r"^[A-Z][A-Z0-9_]*$")
LARGO_NOMBRE_ENV = 32
# env.vars puede estar vacio (kit sin .env); ningun otro artefacto.
PUEDE_ESTAR_VACIO = ("env.vars",)


class RespaldoError(Exception):
    """Error con codigo de salida para el operador."""

    def __init__(self, mensaje: str, codigo: int = 2) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_archivo(path) -> str:
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def escribir_texto_seguro(destino, texto, modo=0o600):
    """Escribe un fichero sin seguir enlaces simbolicos.

    Un enlace en el destino permitiria sobrescribir cualquier fichero del
    sistema (por ejemplo el .env del kit) sin alterar los checksums del
    respaldo: el enlace se rechaza en vez de seguirlo.
    """
    destino = Path(destino)
    if destino.is_symlink():
        raise RespaldoError("No se escribe sobre un enlace simbolico: " + str(destino), 2)
    if destino.exists() and not destino.is_file():
        raise RespaldoError("El destino no es un fichero regular: " + str(destino), 2)
    destino.write_text(texto, encoding="utf-8")
    os.chmod(destino, modo)
    return destino


def escribir_json(destino, datos, modo=0o600):
    """Escribe JSON sin seguir enlaces simbolicos."""
    return escribir_texto_seguro(destino, json.dumps(datos, indent=2, ensure_ascii=False) + "\n",
                                  modo)


def artefactos_presentes(destino):
    """Rutas relativas de los archivos del respaldo, lista para el manifiesto."""
    destino = Path(destino)
    lista = []
    for p in destino.rglob("*"):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise RespaldoError("Artefacto no regular en el respaldo", 2)
        if not p.is_file():
            continue
        relativa = str(p.relative_to(destino))
        if relativa in ("manifest.json", "restore-report.json"):
            continue
        lista.append(relativa)
    return sorted(lista)


def hash_arbol(destino, nombres):
    """sha256 de cada artefacto indicado. Falla si falta alguno."""
    destino = Path(destino)
    digests = {}
    for nombre in nombres:
        p = destino / nombre
        if p.is_symlink() or not p.is_file():
            raise RespaldoError("Artefacto ausente o no regular: " + nombre, 2)
        digests[nombre] = sha256_archivo(p)
    return digests


def receptor_age() -> str:
    """Clave publica del receptor configurada en el entorno."""
    for var in VARS_RECIPIENTE:
        valor = os.environ.get(var, "").strip()
        if valor:
            return valor
    return ""


def nombres_env(texto) -> list:
    """Nombres de variable de un .env, sin valores y sin continuaciones.

    Solo se aceptan lineas con forma de asignacion valida. Las lineas de
    continuacion (un valor multilinea entre comillas) se descartan: si no, un
    fragmento de clave PEM o de base64 terminado en '=' acabaria en env.vars
    y el respaldo filtraria parte del secreto.
    """
    nombres = []
    en_valor = False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#"):
            continue
        if en_valor:
            # Continuacion del valor multilinea: solo importa cerrar la comilla.
            if '"' in limpia or "'" in limpia:
                en_valor = False
            continue
        match = ASIGNACION_ENV.match(limpia)
        if not match:
            continue
        nombre = match.group(1)
        if len(nombre) > LARGO_NOMBRE_ENV and not NOMBRE_ENV_LARGO.match(nombre):
            # Fragmento de base64 o PEM, no un nombre de variable.
            continue
        resto = limpia[match.end():]
        if resto.count('"') % 2 == 1 or resto.count("'") % 2 == 1:
            en_valor = True
        if nombre not in nombres:
            nombres.append(nombre)
    return sorted(nombres)


def exportar_env(root, destino) -> dict:
    """Escribe env.vars (nombres) y, si hay receptor age, env.age (cifrado).

    El .env jamas se escribe en claro. Sin receptor age el respaldo sale sin el
    .env y el manifiesto lo declara: no existe modo degradado a texto plano.
    """
    root = Path(root)
    destino = Path(destino)
    origen = root / ".env"
    if not origen.is_file():
        escribir_texto_seguro(destino / "env.vars", "")
        return {"env": "env.vars", "env_vars": 0, "env_cifrado": False,
                "env_nota": "el kit no tiene .env"}
    unicos = nombres_env(origen.read_text(encoding="utf-8", errors="replace"))
    escribir_texto_seguro(destino / "env.vars", "\n".join(unicos) + ("\n" if unicos else ""))
    meta = {"env": "env.vars", "env_vars": len(unicos), "env_cifrado": False}
    receptor = receptor_age()
    if not receptor:
        meta["env_nota"] = "sin receptor age: el .env no viaja en el respaldo"
        return meta
    if shutil.which("age") is None:
        raise RespaldoError("age no esta disponible y hay receptor configurado: "
                            "no hay modo degradado en claro", 5)
    destino_age = destino / "env.age"
    if destino_age.is_symlink():
        raise RespaldoError("No se escribe sobre un enlace simbolico: " + str(destino_age), 2)
    proc = subprocess.run(["age", "-r", receptor, "-o", str(destino_age)],
                          input=origen.read_bytes(), capture_output=True)
    if proc.returncode != 0:
        detalle = proc.stderr.decode("utf-8", "replace").strip()
        raise RespaldoError("age no pudo cifrar el .env: " + detalle, 5)
    meta["env"] = "env.age"
    meta["env_cifrado"] = True
    return meta


def cifrar_con_age(productor, destino, receptor):
    """Cifra con age la salida de un productor.

    productor recibe el flujo de entrada: el texto plano nunca se escribe en
    disco, va directo del productor al cifrador.
    """
    if shutil.which("age") is None:
        raise RespaldoError("age no esta disponible y hay receptor configurado: "
                            "no hay modo degradado en claro", 5)
    with open(destino, "wb") as salida:
        proceso = subprocess.Popen(["age", "-r", receptor], stdin=subprocess.PIPE, stdout=salida)
        try:
            productor(proceso.stdin)
        finally:
            try:
                proceso.stdin.close()
            finally:
                codigo = proceso.wait()
    if codigo != 0:
        raise RespaldoError("age no pudo cifrar el volumen sensible", 5)


def descifrar_con_age(origen, destino, identidad=None):
    """Descifra con age usando la clave privada del receptor.

    La clave privada es un insumo externo (la custodia del receptor): si no
    esta, la restauracion se detiene con un motivo explicito.
    """
    if shutil.which("age") is None:
        raise RespaldoError("age no esta disponible: no se puede restaurar el volumen sensible", 5)
    identidad = identidad or os.environ.get("AGE_IDENTITY_FILE", "")
    if not identidad:
        raise RespaldoError("Falta la clave privada age del receptor (AGE_IDENTITY_FILE): "
                            "es un insumo externo y no se genera aqui", 5)
    with Path(origen).open("rb") as origen_flujo, Path(destino).open("wb") as destino_flujo:
        proc = subprocess.run(["age", "-d", "-i", identidad],
                              stdin=origen_flujo, stdout=destino_flujo)
    if proc.returncode != 0:
        raise RespaldoError("age no pudo descifrar el volumen sensible", 5)


def marcar_fallido(destino, software, version, database):
    """Escribe un manifiesto no restaurable cuando el respaldo se interrumpe."""
    destino = Path(destino)
    manifiesto = {"software": software, "version": version, "database": database,
                  "sha256": {}, "status": "failed",
                  "failed_at": ahora()}
    escribir_json(destino / "manifest.json", manifiesto)
    return manifiesto


def escribir_manifiesto(destino, software, version, database, artefactos, extra=None) -> dict:
    """Escribe manifest.json con las cinco claves del contrato."""
    destino = Path(destino)
    manifiesto = {
        "software": software,
        "version": version,
        "database": database,
        "sha256": hash_arbol(destino, artefactos),
        "status": "completed",
        "created_at": ahora(),
    }
    if extra:
        manifiesto.update(extra)
    escribir_json(destino / "manifest.json", manifiesto)
    return manifiesto


def leer_manifiesto(destino):
    destino = Path(destino)
    archivo = destino / "manifest.json"
    if archivo.is_symlink() or not archivo.is_file():
        raise RespaldoError("Falta manifest.json: el respaldo no es restaurable", 2)
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RespaldoError("manifest.json ilegible: " + str(exc), 2)
    if not isinstance(datos, dict):
        raise RespaldoError("manifest.json no es un objeto JSON", 2)
    faltantes = [clave for clave in CLAVES_MANIFIESTO if clave not in datos]
    if faltantes:
        raise RespaldoError("manifest.json sin claves: " + ", ".join(faltantes), 2)
    if datos.get("status") != "completed":
        raise RespaldoError("El respaldo no esta completado (status distinto de completed): "
                            "no se restaura", 2)
    return datos


def verificar_checksums(destino, manifiesto=None, esperados=()):
    """Comprueba sha256 de cada artefacto del manifiesto.

    esperados son los artefactos obligatorios: el manifiesto tiene que
    declararlos siempre. Sin ellos el respaldo no es comprobable.
    """
    destino = Path(destino).resolve()
    manifiesto = manifiesto or leer_manifiesto(destino)
    digests = manifiesto.get("sha256")
    if not isinstance(digests, dict) or not digests:
        raise RespaldoError("manifest.json sin sha256 de artefactos", 2)
    if not esperados:
        raise RespaldoError("El contrato exige declarar los artefactos obligatorios", 2)
    faltantes = sorted(set(esperados) - set(digests))
    if faltantes:
        raise RespaldoError("El manifiesto no declara los artefactos obligatorios: "
                            + ", ".join(faltantes), 2)
    for nombre, digest in digests.items():
        ruta = PurePosixPath(nombre)
        if (not nombre or ruta.is_absolute() or ".." in ruta.parts or "\\" in nombre
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise RespaldoError("Ruta o digest no admitido en el manifiesto", 2)
        p = (destino / nombre)
        if p.is_symlink() or not p.is_file():
            raise RespaldoError("Artefacto ausente o no regular: " + nombre, 2)
        if not str(p.resolve()).startswith(str(destino) + os.sep):
            raise RespaldoError("Ruta no admitida en el manifiesto: " + nombre, 2)
        if sha256_archivo(p) != digest:
            raise RespaldoError("Checksum incorrecto: " + nombre, 2)
    return manifiesto


def verificar_cobertura(destino, manifiesto):
    """El manifiesto debe cubrir exactamente los archivos presentes en el respaldo."""
    destino = Path(destino)
    declarados = set(manifiesto.get("sha256") or {})
    reales = set()
    for p in destino.rglob("*"):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise RespaldoError("Artefacto no regular en el respaldo", 2)
        if not p.is_file():
            continue
        relativa = str(p.relative_to(destino))
        if relativa in ("manifest.json", "restore-report.json"):
            continue
        reales.add(relativa)
    if declarados != reales:
        faltantes = sorted(reales - declarados)
        sobrantes = sorted(declarados - reales)
        raise RespaldoError("El manifiesto no cubre los archivos del respaldo "
                            "(sin declarar: " + ", ".join(faltantes) +
                            "; declarados y ausentes: " + ", ".join(sobrantes) + ")", 2)
    return manifiesto


def detectar_secreto_en_claro(destino):
    """Nombre del archivo de secretos en claro dentro del respaldo, o None."""
    destino = Path(destino)
    if not destino.is_dir():
        return None
    for p in sorted(destino.rglob("*")):
        if not p.is_file():
            continue
        nombre = p.name.lower()
        if nombre == ".env" or nombre.endswith(".env") or nombre.startswith(".env."):
            if nombre != ".env.example":
                return nombre
    return None


def ejecutar_check(destino, software, version, database, esperados, prohibidos=(),
                   requeridos=(), excluibles=()):
    """Verificacion completa de un respaldo. Lanza RespaldoError con su codigo.

    esperados: artefactos que produce el kit. Cada uno tiene que estar en el
      manifiesto o su exclusion tiene que estar declarada en "excluidos": un
      manifiesto que solo declara env.vars no es un respaldo verificable.
    requeridos: artefactos que ademas no pueden estar vacios.
    excluibles: {clave del manifiesto: artefacto} que puede faltar solo si el
      manifiesto declara esa exclusion en "excluidos".
    prohibidos: nombres de archivo que no pueden estar en claro en el respaldo
    (por ejemplo el volumen de configuracion de un servicio con token de API).
    """
    destino = Path(destino)
    if not destino.is_dir():
        raise RespaldoError("El respaldo no existe o no es un directorio", 2)
    manifiesto = leer_manifiesto(destino)
    if (manifiesto.get("software"), manifiesto.get("version"),
            manifiesto.get("database")) != (software, version, database):
        raise RespaldoError("El manifiesto no corresponde a este kit", 2)
    secreto = detectar_secreto_en_claro(destino)
    if secreto:
        raise RespaldoError("El respaldo contiene material sensible en claro: " + secreto, 4)
    for nombre in prohibidos:
        if (destino / nombre).exists():
            raise RespaldoError("El respaldo contiene material sensible en claro: " + nombre, 4)
    declarados = set(manifiesto.get("sha256") or {})
    excluidos = manifiesto.get("excluidos") or []
    if not isinstance(excluidos, list):
        raise RespaldoError("El manifiesto declara 'excluidos' en un formato no admitido", 2)
    mapa = dict(excluibles)
    for clave, artefacto in mapa.items():
        if clave in excluidos and artefacto in declarados:
            raise RespaldoError("El manifiesto declara excluido " + artefacto +
                                " pero lo incluye en el respaldo", 2)
    excluidos_artefactos = {artefacto for clave, artefacto in mapa.items() if clave in excluidos}
    obligatorios = [nombre for nombre in esperados if nombre not in excluidos_artefactos]
    if not obligatorios:
        raise RespaldoError("El kit no declara ningun artefacto obligatorio", 2)
    faltan = [nombre for nombre in obligatorios if nombre not in declarados]
    if faltan:
        raise RespaldoError("El manifiesto no declara los artefactos obligatorios: "
                            + ", ".join(faltan) + " (y no declara su exclusion)", 2)
    verificar_checksums(destino, manifiesto, obligatorios)
    verificar_cobertura(destino, manifiesto)
    for nombre in requeridos:
        if nombre not in declarados:
            raise RespaldoError("Falta artefacto requerido: " + nombre, 2)
    for nombre in sorted(declarados):
        if nombre in PUEDE_ESTAR_VACIO:
            continue
        if (destino / nombre).stat().st_size == 0:
            raise RespaldoError("Artefacto vacio: " + nombre, 2)
    return manifiesto


def opciones_restore(argv):
    """Interpreta --dry-run y --confirmar CONFIRMAR_RESTAURACION.

    Sin --confirmar ni --dry-run la restauracion no se ejecuta: el operador
    tiene que pedirla de forma explicita.
    """
    modo = None
    destino = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--dry-run":
            if modo == "confirmado":
                raise RespaldoError("No se pueden combinar --dry-run y --confirmar", 1)
            modo = "dry-run"
        elif arg == "--confirmar":
            if i + 1 >= len(argv):
                raise RespaldoError("Falta el valor de --confirmar", 1)
            if argv[i + 1] != CONFIRMACION:
                raise RespaldoError("El valor de --confirmar debe ser " + CONFIRMACION, 1)
            if modo == "dry-run":
                raise RespaldoError("No se pueden combinar --dry-run y --confirmar", 1)
            modo = "confirmado"
            i += 1
        elif arg.startswith("-"):
            raise RespaldoError("Opcion desconocida: " + arg, 1)
        else:
            if destino is not None:
                raise RespaldoError("Solo se admite un directorio de respaldo", 1)
            destino = arg
        i += 1
    if destino is None:
        raise RespaldoError("Uso: python3 scripts/restore.py /ruta/respaldo "
                            "[--dry-run|--confirmar " + CONFIRMACION + "]", 1)
    if modo is None:
        raise RespaldoError("Falta --confirmar " + CONFIRMACION +
                            " (o --dry-run para simular sin escribir)", 3)
    return modo, destino


def auditar(root, **campos):
    """Registro append-only de actividades de tratamiento (nunca valores de secretos)."""
    logs = Path(root) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    registro = {"ts": ahora(), **campos}
    destino = logs / "restore.log"
    with destino.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    os.chmod(destino, 0o600)


def escribir_informe(carpeta, **campos):
    """Informe de restauracion junto al respaldo.

    El informe nunca se escribe siguiendo un enlace simbolico: un enlace en
    el respaldo permitiria sobrescribir cualquier fichero del sistema.
    """
    destino = Path(carpeta)
    informe = {"ts": ahora(), **campos}
    escribir_json(destino / "restore-report.json", informe)
    return informe


def ejecutar(funcion):
    """Traduce RespaldoError al codigo de salida documentado."""
    try:
        return funcion()
    except RespaldoError as exc:
        print(str(exc), file=sys.stderr)
        return exc.codigo


def validar_tar(archivo):
    """Valida todo el tar antes de escribir: rutas, tipos, duplicados y lectura."""
    vistos = set()
    try:
        with tarfile.open(archivo, "r:gz") as tf:
            for miembro in tf:
                ruta = PurePosixPath(miembro.name)
                if (ruta.is_absolute() or ".." in ruta.parts or str(ruta) in vistos
                        or not (miembro.isfile() or miembro.isdir())):
                    raise RespaldoError("Ruta, tipo o duplicado no admitido en tar", 5)
                vistos.add(str(ruta))
                if miembro.isfile():
                    with tf.extractfile(miembro) as flujo:
                        while flujo.read(1024 * 1024):
                            pass
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise RespaldoError("Archivo tar ilegible o truncado", 5) from exc


@contextmanager
def auditoria_restore(root, origen, manifiesto):
    """Registra resultado y hashes ya verificados, sin datos ni secretos."""
    campos = {"operacion": "restore", "kit": manifiesto["software"],
              "origen": str(origen), "destino": str(root),
              "sha256": manifiesto["sha256"]}
    try:
        yield
    except Exception:
        auditar(root, **campos, resultado="failed")
        raise
    else:
        auditar(root, **campos, resultado="restaurado")
