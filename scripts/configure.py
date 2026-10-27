#!/usr/bin/env python3
import os,secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'.env.example').read_text().replace('GENERAR_CON_SCRIPT',secrets.token_hex(32),1).replace('GENERAR_CON_SCRIPT',secrets.token_hex(48),1)
try:fd=os.open(root/'.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
except FileExistsError:raise SystemExit('Ya existe .env; no se sobrescribe')
with os.fdopen(fd,'w') as f:f.write(s)
print('.env creado con permisos 0600. Edite host, URL y confirmaciones; asigne DB_PASSWORD al rol vikunja_app.')
