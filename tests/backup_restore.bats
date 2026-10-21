#!/usr/bin/env bats
load 'ayudante'

setup() {
  preparar_kit
  preparar_datos
  generar_receptor_age
}

teardown() {
  : # Bats gestiona exclusivamente sus fixtures sinteticos
}

@test "el respaldo genera manifest.json con las cinco claves del contrato" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ -f "$RESPALDO/manifest.json" ]
  run python3 -c "import json,sys; m=json.load(open(sys.argv[1])); falta=[k for k in ('software','version','database','sha256','status') if k not in m]; assert not falta, falta; assert m['status']=='completed', m['status']; assert m['software']=='hefesto-tareas', m['software']; assert m['database']=='postgresql', m['database']" "$RESPALDO/manifest.json"
  [ "$status" -eq 0 ]
}

@test "el .env no queda en claro en el respaldo" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ ! -f "$RESPALDO/.env" ]
  [ -f "$RESPALDO/env.vars" ]
  run grep -R -F "valor-ficticio-no-real" "$RESPALDO"
  [ "$status" -ne 0 ]
}

@test "con receptor age el .env viaja cifrado" {
  if [ -z "${AGE_RECIPIENT:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ -f "$RESPALDO/env.age" ]
  run grep -R -F "valor-ficticio-no-real" "$RESPALDO"
  [ "$status" -ne 0 ]
}

@test "el material personal viaja cifrado y no en claro" {
  if [ -z "${AGE_RECIPIENT:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ -f "$RESPALDO/files.tar.gz.age" ]
  [ ! -f "$RESPALDO/files.tar.gz" ]
}

@test "el dump de la base viaja cifrado y nunca en claro" {
  if [ -z "${AGE_RECIPIENT:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ -f "$RESPALDO/public.dump.age" ]
  [ ! -f "$RESPALDO/public.dump" ]
  run python3 -c "import json,sys; m=json.load(open(sys.argv[1])); assert m['sha256'].get('public.dump.age'), m; assert 'public.dump' not in m['sha256'], m" "$RESPALDO/manifest.json"
  [ "$status" -eq 0 ]
}

@test "sin receptor age el dump no viaja y el manifiesto lo declara" {
  export SOPS_AGE_RECIPIENT=""
  export AGE_RECIPIENT=""
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ ! -f "$RESPALDO/public.dump" ]
  [ ! -f "$RESPALDO/public.dump.age" ]
  run python3 -c "import json,sys; m=json.load(open(sys.argv[1])); assert 'dump' in m.get('excluidos',[]), m; assert m['dump'].startswith('excluido'), m" "$RESPALDO/manifest.json"
  [ "$status" -eq 0 ]
}

@test "env.vars no filtra un secreto multilinea" {
  CABECERA="-----BEGIN ""PRIVATE KEY-----"
  printf 'DUMMY_SECRET=valor-ficticio-no-real\nCLAVE_PRIVADA="%s\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ==\n-----END PRIVATE KEY-----"\nPUBLIC_URL=https://example.invalid\n' "$CABECERA" > "$KIT/.env"
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  [ -f "$RESPALDO/env.vars" ]
  run grep -F "MIIEvQ" "$RESPALDO/env.vars"
  [ "$status" -ne 0 ]
  run grep -F "PRIVATE KEY" "$RESPALDO/env.vars"
  [ "$status" -ne 0 ]
  run grep -F "CLAVE_PRIVADA" "$RESPALDO/env.vars"
  [ "$status" -eq 0 ]
}

@test "check_backup acepta el respaldo integro" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 0 ]
}

@test "check_backup rechaza un artefacto alterado" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  printf 'alterado\n' >> "$RESPALDO/public.dump.age"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 2 ]
}

@test "check_backup rechaza un dump en claro dentro del respaldo" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  printf 'material personal\n' > "$RESPALDO/public.dump"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 4 ]
}

@test "check_backup rechaza un manifiesto que solo declara env.vars" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  run python3 -c "import json,sys,pathlib; b=pathlib.Path(sys.argv[1]); m=json.loads((b/'manifest.json').read_text()); m['sha256']={'env.vars': m['sha256']['env.vars']}; m['excluidos']=[]; (b/'manifest.json').write_text(json.dumps(m))" "$RESPALDO"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 2 ]
}

@test "check_backup rechaza un .env en claro dentro del respaldo" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  cp "$KIT/.env" "$RESPALDO/.env"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 4 ]
}

@test "check_backup rechaza el material personal en claro" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  printf 'material personal
' > "$RESPALDO/files.tar.gz"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 4 ]
}

@test "check_backup rechaza un respaldo no completado" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  python3 -c "import json,sys; p=sys.argv[1]; m=json.load(open(p)); m['status']='failed'; json.dump(m, open(p,'w'))" "$RESPALDO/manifest.json"
  run python3 "$KIT/scripts/check_backup.py" "$RESPALDO"
  [ "$status" -eq 2 ]
}

@test "restore en dry-run no escribe nada" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_db.py" "$RESPALDO" --dry-run
  [ "$status" -eq 0 ]
  [ ! -f "$RESPALDO/restore-report.json" ]
  [ ! -d "$KIT/logs" ]
}

@test "restore sin --confirmar no restaura" {
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_db.py" "$RESPALDO"
  [ "$status" -eq 3 ]
  [ ! -f "$RESPALDO/restore-report.json" ]
}

@test "restore con --confirmar restaura y deja informe y auditoria" {
  if [ -z "${AGE_IDENTITY_FILE:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_db.py" "$RESPALDO" --confirmar CONFIRMAR_RESTAURACION
  [ "$status" -eq 0 ]
  [ -f "$RESPALDO/restore-report.json" ]
  [ -f "$KIT/logs/restore.log" ]
  run grep -F "restore" "$KIT/logs/restore.log"
  [ "$status" -eq 0 ]
  run grep -F "restaurado" "$KIT/logs/restore.log"
  [ "$status" -eq 0 ]
}

@test "restore de los volumenes deja informe y auditoria" {
  if [ -z "${AGE_IDENTITY_FILE:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_files.py" "$RESPALDO" --confirmar CONFIRMAR_RESTAURACION
  [ "$status" -eq 0 ]
  [ -f "$RESPALDO/restore-report.json" ]
  [ -f "$KIT/logs/restore.log" ]
  run grep -F "volumenes-restaurados" "$RESPALDO/restore-report.json"
  [ "$status" -eq 0 ]
}

@test "la auditoria registra los hashes verificados y el resultado" {
  if [ -z "${AGE_IDENTITY_FILE:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_db.py" "$RESPALDO" --confirmar CONFIRMAR_RESTAURACION
  [ "$status" -eq 0 ]
  run python3 -c "import json,sys; r=[json.loads(l) for l in open(sys.argv[1])]; assert r, r; u=r[-1]; assert u['resultado']=='restaurado', u; assert u['sha256'], u; assert 'public.dump.age' in u['sha256'], u" "$KIT/logs/restore.log"
  [ "$status" -eq 0 ]
  run grep -F "valor-ficticio-no-real" "$KIT/logs/restore.log"
  [ "$status" -ne 0 ]
}

@test "restore aborta si el destino no esta vacio" {
  if [ -z "${AGE_IDENTITY_FILE:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  export STUB_RUNNING=0
  export STUB_FIND_OUTPUT="dato-previo.txt"
  run python3 "$KIT/scripts/restore_files.py" "$RESPALDO" --confirmar CONFIRMAR_RESTAURACION
  [ "$status" -eq 5 ]
  [ ! -f "$RESPALDO/restore-report.json" ]
}

@test "restore no escribe nada si falta el volumen cifrado" {
  if [ -z "${AGE_IDENTITY_FILE:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  rm "$RESPALDO/files.tar.gz.age"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_files.py" "$RESPALDO" --confirmar CONFIRMAR_RESTAURACION
  [ "$status" -eq 2 ]
  [ ! -f "$RESPALDO/restore-report.json" ]
}

@test "restore no escribe nada si la identidad age es incorrecta" {
  if [ -z "${AGE_IDENTITY_FILE:-}" ]; then skip "age-keygen no disponible en este entorno"; fi
  run python3 "$KIT/scripts/backup.py"
  [ "$status" -eq 0 ]
  RESPALDO="$(ls -d "$KIT"/backups/*/ | head -1)"
  age-keygen -o "$BATS_TEST_TMPDIR/otra-clave.txt" >/dev/null 2>&1
  export AGE_IDENTITY_FILE="$BATS_TEST_TMPDIR/otra-clave.txt"
  export STUB_RUNNING=0
  run python3 "$KIT/scripts/restore_files.py" "$RESPALDO" --confirmar CONFIRMAR_RESTAURACION
  [ "$status" -eq 5 ]
  [ ! -f "$RESPALDO/restore-report.json" ]
}
