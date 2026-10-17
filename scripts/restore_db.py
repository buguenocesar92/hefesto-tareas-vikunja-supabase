#!/usr/bin/env python3
"""Restore only the Vikunja public-schema archive into an empty prepared project."""
import hashlib,json,os,re,subprocess,sys,tempfile
from pathlib import Path
if len(sys.argv)!=2:raise SystemExit('Uso: python3 scripts/restore_db.py /ruta/respaldo')
backup=Path(sys.argv[1]).resolve();root=Path(__file__).resolve().parents[1];os.chdir(root)
manifest=json.loads((backup/'manifest.json').read_text());dump=backup/'public.dump'
if manifest.get('product')!='hefesto-tareas':raise SystemExit('Producto incorrecto')
if manifest.get('version')!='2.7.0' or manifest.get('status')!='completed':raise SystemExit('Manifest/version no valido')
with dump.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
if digest!=manifest['sha256']['public.dump']:raise SystemExit('Checksum incorrecto')
def dc(*args,**kw):return subprocess.run(['docker','compose',*args],check=True,**kw)
for service in ['app']:
    if dc('ps','--status','running','-q',service,capture_output=True,text=True).stdout.strip():
        raise SystemExit('Detener Vikunja antes de restaurar en destino nuevo')
count=dc('run','--rm','--no-deps','-T','--entrypoint','psql','dbtools','-Atc',"SELECT count(*) FROM pg_tables WHERE schemaname='public'",capture_output=True,text=True).stdout.strip()
if count!='0':raise SystemExit('public no esta vacio; no se sobrescribiran datos')
with dump.open('rb') as stream:
    toc=dc('run','--rm','--no-deps','-T','--entrypoint','pg_restore','dbtools','--list',stdin=stream,stdout=subprocess.PIPE).stdout.decode()
# public already exists in Supabase. Do not drop it or restore its SCHEMA creation entry.
lines=[line for line in toc.splitlines() if not re.match(r'^\d+;\s+\d+\s+\d+\s+SCHEMA\s+-\s+public(?:\s|$)',line)]
with tempfile.TemporaryDirectory(prefix='hefesto-restore-') as d:
    path=Path(d)/'restore.list';path.write_text('\n'.join(lines)+'\n');os.chmod(d,0o755);os.chmod(path,0o644)
    with dump.open('rb') as stream:
        dc('run','--rm','--no-deps','-T','-v',d+':/restore:ro','--entrypoint','pg_restore','dbtools','--exit-on-error','--no-owner','--no-acl','--use-list=/restore/restore.list','--dbname=postgres',stdin=stream)
print('Base restaurada. Restaure archivos antes de iniciar Vikunja.')
