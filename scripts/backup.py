#!/usr/bin/env python3
import datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];os.chdir(root);os.umask(0o077)
def dc(*a,**kw):return subprocess.run(['docker','compose',*a],check=True,**kw)
p=root/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');p.mkdir(parents=True,mode=0o700)
running=bool(dc('ps','--status','running','-q','app',capture_output=True,text=True).stdout.strip())
try:
    dc('stop','app')
    with (p/'public.dump').open('wb') as f:dc('run','--rm','--no-deps','-T','--entrypoint','pg_dump','dbtools','--format=custom','--schema=public','--no-owner','--no-acl',stdout=f)
    with (p/'files.tar.gz').open('wb') as f:dc('run','--rm','--no-deps','-T','--entrypoint','tar','filetools','-czf','-','-C','/files','.',stdout=f)
    shutil.copy2(root/'.env',p/'.env');shutil.copy2(root/'compose.yaml',p/'compose.yaml')
    hashes={}
    for n in ['public.dump','files.tar.gz','.env','compose.yaml']:
        with (p/n).open('rb') as f:hashes[n]=hashlib.file_digest(f,'sha256').hexdigest()
    (p/'manifest.json').write_text(json.dumps({'product':'hefesto-tareas','version':'2.7.0','status':'completed','sha256':hashes},indent=2))
    print('Respaldo completo:',p,'Contiene secretos; cifrar antes de transferir.')
finally:
    if running:dc('start','app')
