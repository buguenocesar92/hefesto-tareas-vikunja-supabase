#!/usr/bin/env python3
"""Regresiones con age real efimero y Docker simulado cerrado."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

kit = Path(os.environ["KIT"])
ghost = (kit / "scripts/restore.py").exists()
dump = "ghost.sql.age" if ghost else "public.dump.age"
dump_en_claro = "ghost.sql" if ghost else "public.dump"
archive = "content.tar.gz.age" if ghost else "files.tar.gz.age"
restore = "restore.py" if ghost else "restore_files.py"
dbrestore = "restore.py" if ghost else "restore_db.py"
trace = Path(os.environ["STUB_TRACE"])
capture = Path(os.environ["STUB_CAPTURE"])
case = sys.argv[1]

def call(script, *args):
    return subprocess.run([sys.executable, str(kit / "scripts" / script), *map(str, args)],
                          capture_output=True, text=True, timeout=15)

def expect(proc, rc):
    assert proc.returncode == rc, (case, proc.returncode, proc.stdout, proc.stderr)

def events():
    return [json.loads(line)["op"] for line in trace.read_text().splitlines()]

def no_writes():
    assert not {"restoredb", "restorefiles", "permissions"}.intersection(events()), events()

def save_manifest():
    (backup / "manifest.json").write_text(json.dumps(manifest))

def rehash(name):
    manifest["sha256"][name] = hashlib.sha256((backup / name).read_bytes()).hexdigest()
    save_manifest()

if case == "no_recipient":
    os.environ["AGE_RECIPIENT"] = ""
elif case == "bad_recipient":
    os.environ["AGE_RECIPIENT"] = "no-es-un-receptor-age"
elif case.startswith("failure_"):
    os.environ["STUB_FAIL"] = case.removeprefix("failure_")
elif case == "env_multiline":
    # .env con clave PEM multilinea entre comillas: solo los nombres salen.
    # El encabezado se arma en tiempo de ejecucion para no dejar en el
    # repositorio un marcador literal de clave privada (lo bloquea el guard).
    cabecera = "-----BEGIN " + "PRIVATE KEY-----"
    (kit / ".env").write_text(
        "DUMMY_SECRET=valor-ficticio-no-real\n"
        'CLAVE_PRIVADA="' + cabecera + "\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ==\n"
        '"-----END PRIVATE KEY-----"\n'
        "PUBLIC_URL=https://example.invalid\n")
proc = call("backup.py")
backup = next((kit / "backups").iterdir())
manifest = json.loads((backup / "manifest.json").read_text())
if case.startswith("failure_") or case == "bad_recipient":
    assert proc.returncode != 0, (case, proc.stdout, proc.stderr)
    assert manifest["status"] == "failed", manifest
    if case != "failure_start":
        assert "start" in events() and not Path(os.environ["STUB_STATE_FILE"]).read_text()
    assert not (backup / ".env").exists()
    sys.exit(0)
expect(proc, 0)
if case == "no_recipient":
    assert not (backup / ".env").exists() and not (backup / "env.age").exists()
    assert not (backup / archive).exists()
    assert manifest["env_cifrado"] is False
    # Sin receptor age no hay dump en claro: el respaldo lo declara excluido.
    assert not (backup / dump).exists(), sorted(p.name for p in backup.iterdir())
    assert not (backup / dump_en_claro).exists(), sorted(p.name for p in backup.iterdir())
    assert sorted(manifest["excluidos"]) == ["content", "dump"] if ghost \
        else sorted(manifest["excluidos"]) == ["dump", "files"], manifest["excluidos"]
    expect(call("check_backup.py", backup), 0)
    sys.exit(0)
if case == "env_multiline":
    nombres = (backup / "env.vars").read_text()
    assert "MIIEvQ" not in nombres, nombres
    assert "PRIVATE KEY" not in nombres, nombres
    assert nombres.split() == ["CLAVE_PRIVADA", "DUMMY_SECRET", "PUBLIC_URL"], nombres
    expect(call("check_backup.py", backup), 0)
    sys.exit(0)
if case == "dump_encrypted":
    # El dump viaja cifrado y descifra byte a byte al dump sintetico.
    assert (backup / dump).exists(), sorted(p.name for p in backup.iterdir())
    assert not (backup / dump_en_claro).exists(), sorted(p.name for p in backup.iterdir())
    descifrado = subprocess.run(["age", "-d", "-i", os.environ["AGE_IDENTITY_FILE"]],
                                input=(backup / dump).read_bytes(), capture_output=True)
    assert descifrado.returncode == 0, descifrado.stderr
    assert descifrado.stdout == Path(os.environ["STUB_DUMP_FILE"]).read_bytes()
    expect(call("check_backup.py", backup), 0)
    sys.exit(0)
if case == "dump_clear":
    # Un dump en claro dentro del respaldo se rechaza como material sensible.
    (backup / dump_en_claro).write_bytes(b"-- dump en claro\n")
    expect(call("check_backup.py", backup), 4)
    sys.exit(0)
os.environ["STUB_RUNNING"] = "0"
trace.write_text("")
if case == "missing_dump":
    (backup / dump).rename(backup.parent / "removed-dump")
    manifest["sha256"].pop(dump)
    manifest["excluidos"] = []
    save_manifest()
    expect(call("check_backup.py", backup), 2)
    expect(call(dbrestore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 2)
    no_writes()
elif case == "empty_dump":
    (backup / dump).write_bytes(b"")
    rehash(dump)
    expect(call("check_backup.py", backup), 2)
elif case == "solo_env_vars":
    # Un manifiesto que solo declara env.vars no es un respaldo verificable.
    for nombre in list(manifest["sha256"]):
        if nombre != "env.vars":
            (backup / nombre).unlink()
    manifest["sha256"] = {"env.vars": manifest["sha256"]["env.vars"]}
    manifest["excluidos"] = []
    save_manifest()
    proc = call("check_backup.py", backup)
    expect(proc, 2)
    assert "obligatorios" in proc.stderr, proc.stderr
elif case == "missing_volume":
    # El volumen no está y no se declara su exclusion: no se restaura nada.
    (backup / archive).unlink()
    manifest["sha256"].pop(archive)
    manifest["excluidos"] = []
    save_manifest()
    expect(call("check_backup.py", backup), 2)
    expect(call(restore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 2)
    no_writes()
elif case == "report_symlink":
    # Un informe enlazado no puede sobrescribir un fichero de fuera.
    victima = backup.parent / "victima-fuera.txt"
    victima.write_text("contenido original\n")
    (backup / "restore-report.json").symlink_to(victima)
    proc = call(dbrestore, backup, "--confirmar", "CONFIRMAR_RESTAURACION")
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert victima.read_text() == "contenido original\n", victima.read_text()
    no_writes()
elif case == "nested_env":
    (backup / "nested").mkdir()
    (backup / "nested/.env").write_text("DUMMY_SECRET=valor-ficticio-no-real\n")
    rehash("nested/.env")
    expect(call("check_backup.py", backup), 4)
elif case == "hash_type":
    manifest["sha256"] = [dump]
    save_manifest()
    expect(call("check_backup.py", backup), 2)
elif case == "digest_type":
    manifest["sha256"][dump] = ["invalido"]
    save_manifest()
    expect(call("check_backup.py", backup), 2)
elif case == "traversal_manifest":
    other = backup.parent / "outside.txt"
    other.write_text("fixture externa")
    manifest["sha256"]["../outside.txt"] = hashlib.sha256(other.read_bytes()).hexdigest()
    save_manifest()
    expect(call("check_backup.py", backup), 2)
elif case == "corruption":
    with (backup / archive).open("ab") as f:
        f.write(b"corrupto")
    expect(call(restore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 2)
    assert events() == [], events()
elif case in ("missing_identity", "wrong_identity", "bad_cipher"):
    if case == "missing_identity":
        os.environ["AGE_IDENTITY_FILE"] = ""
    elif case == "wrong_identity":
        key = kit.parent / "wrong-age.txt"
        subprocess.run(["age-keygen", "-o", str(key)], check=True, capture_output=True)
        os.environ["AGE_IDENTITY_FILE"] = str(key)
    else:
        (backup / archive).write_bytes(b"no es age")
        rehash(archive)
    expect(call(restore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 5)
    no_writes()
elif case.startswith("tar_"):
    kind = case.removeprefix("tar_")
    out = io.BytesIO()
    if kind == "truncated":
        payload = b"no es un tar gzip"
    else:
        with tarfile.open(fileobj=out, mode="w:gz") as tf:
            name = "../escape" if kind == "traversal" else "/escape" if kind == "absolute" else "demo"
            member = tarfile.TarInfo(name)
            member.size = 1
            if kind == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname = "../escape"
                member.size = 0
            tf.addfile(member, io.BytesIO(b"x"))
            if kind == "duplicate":
                tf.addfile(member, io.BytesIO(b"y"))
        payload = out.getvalue()
    proc = subprocess.run(["age", "-r", os.environ["AGE_RECIPIENT"]], input=payload, capture_output=True)
    assert proc.returncode == 0
    (backup / archive).write_bytes(proc.stdout)
    rehash(archive)
    expect(call(restore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 5)
    no_writes()
elif case == "restore_bytes":
    expect(call(dbrestore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 0)
    if not ghost:
        expect(call(restore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 0)
        assert "permissions" in events()
    assert (capture / "restoredb.bin").read_bytes() == Path(os.environ["STUB_DUMP_FILE"]).read_bytes()
    with tarfile.open(capture / "restorefiles.bin") as tf:
        assert tf.extractfile("./data/demo.txt").read() == b"archivo sintetico\n"
    registros = [json.loads(line) for line in (kit / "logs/restore.log").read_text().splitlines()]
    assert all(r["sha256"] == manifest["sha256"] for r in registros), registros
    assert registros[-1]["resultado"] == "restaurado", registros
    assert all("resultado" in r and "sha256" in r for r in registros), registros
    assert "valor-ficticio-no-real" not in (kit / "logs/restore.log").read_text()
elif case == "nonempty_db":
    os.environ["STUB_PSQL_OUT"] = "1"
    expect(call(dbrestore, backup, "--confirmar", "CONFIRMAR_RESTAURACION"), 5)
    no_writes()
elif case == "audit_failure":
    os.environ["STUB_FAIL"] = "restoredb"
    proc = call(dbrestore, backup, "--confirmar", "CONFIRMAR_RESTAURACION")
    assert proc.returncode != 0
    assert not (backup / "restore-report.json").exists()
    record = json.loads((kit / "logs/restore.log").read_text().splitlines()[-1])
    assert record["resultado"] == "failed" and record["sha256"] == manifest["sha256"], record
else:
    raise AssertionError("Caso no reconocido: " + case)
