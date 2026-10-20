# Fixtures sinteticos: nunca lee .env real ni invoca Docker real.
RAIZ="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
export RAIZ
export HEFESTO_KIT_TEST=1
export PATH="$RAIZ/tests/stubs:$PATH"

preparar_kit() {
  KIT="$BATS_TEST_TMPDIR/kit"
  mkdir -p "$KIT/scripts" "$KIT/backups"
  cp "$RAIZ"/scripts/*.py "$KIT/scripts/"
  cp "$RAIZ/compose.yaml" "$KIT/compose.yaml"
  printf 'DUMMY_SECRET=valor-ficticio-no-real\nPUBLIC_URL=https://example.invalid\n' > "$KIT/.env"
  chmod 600 "$KIT/.env"
  export KIT
}

preparar_datos() {
  export STUB_DUMP_FILE="$BATS_TEST_TMPDIR/dump.sql"
  printf -- '-- dump sintetico\nCREATE TABLE demo(id int);\n' > "$STUB_DUMP_FILE"
  export STUB_TAR_DIR="$BATS_TEST_TMPDIR/tar"
  mkdir -p "$STUB_TAR_DIR/data" "$BATS_TEST_TMPDIR/captured"
  printf 'archivo sintetico\n' > "$STUB_TAR_DIR/data/demo.txt"
  export STUB_RUNNING=1 STUB_FIND_OUTPUT="" STUB_PSQL_OUT=0 STUB_FAIL=""
  export STUB_STATE_FILE="$BATS_TEST_TMPDIR/servicios-detenidos"
  export STUB_TRACE="$BATS_TEST_TMPDIR/trace.jsonl"
  export STUB_CAPTURE="$BATS_TEST_TMPDIR/captured"
  : > "$STUB_STATE_FILE"
  : > "$STUB_TRACE"
  export SOPS_AGE_RECIPIENT=""
}

generar_receptor_age() {
  local dir="$BATS_TEST_TMPDIR/age"
  mkdir -p "$dir"
  chmod 700 "$dir"
  age-keygen -o "$dir/clave.txt" >/dev/null 2>&1 || return 1
  AGE_RECIPIENT="$(age-keygen -y "$dir/clave.txt")" || return 1
  export AGE_RECIPIENT AGE_IDENTITY_FILE="$dir/clave.txt"
}
