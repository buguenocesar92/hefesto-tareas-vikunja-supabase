#!/usr/bin/env bats
load 'ayudante'
setup() {
  preparar_kit
  preparar_datos
  generar_receptor_age
}

@test "regresion failure_dump" {
  run python3 "$RAIZ/tests/regression.py" failure_dump
  [ "$status" -eq 0 ]
}

@test "regresion failure_archive" {
  run python3 "$RAIZ/tests/regression.py" failure_archive
  [ "$status" -eq 0 ]
}

@test "regresion failure_start" {
  run python3 "$RAIZ/tests/regression.py" failure_start
  [ "$status" -eq 0 ]
}

@test "regresion bad_recipient" {
  run python3 "$RAIZ/tests/regression.py" bad_recipient
  [ "$status" -eq 0 ]
}

@test "regresion no_recipient" {
  run python3 "$RAIZ/tests/regression.py" no_recipient
  [ "$status" -eq 0 ]
}

@test "regresion env_multiline" {
  run python3 "$RAIZ/tests/regression.py" env_multiline
  [ "$status" -eq 0 ]
}

@test "regresion dump_encrypted" {
  run python3 "$RAIZ/tests/regression.py" dump_encrypted
  [ "$status" -eq 0 ]
}

@test "regresion dump_clear" {
  run python3 "$RAIZ/tests/regression.py" dump_clear
  [ "$status" -eq 0 ]
}

@test "regresion missing_dump" {
  run python3 "$RAIZ/tests/regression.py" missing_dump
  [ "$status" -eq 0 ]
}

@test "regresion empty_dump" {
  run python3 "$RAIZ/tests/regression.py" empty_dump
  [ "$status" -eq 0 ]
}

@test "regresion solo_env_vars" {
  run python3 "$RAIZ/tests/regression.py" solo_env_vars
  [ "$status" -eq 0 ]
}

@test "regresion missing_volume" {
  run python3 "$RAIZ/tests/regression.py" missing_volume
  [ "$status" -eq 0 ]
}

@test "regresion report_symlink" {
  run python3 "$RAIZ/tests/regression.py" report_symlink
  [ "$status" -eq 0 ]
}

@test "regresion nested_env" {
  run python3 "$RAIZ/tests/regression.py" nested_env
  [ "$status" -eq 0 ]
}

@test "regresion hash_type" {
  run python3 "$RAIZ/tests/regression.py" hash_type
  [ "$status" -eq 0 ]
}

@test "regresion digest_type" {
  run python3 "$RAIZ/tests/regression.py" digest_type
  [ "$status" -eq 0 ]
}

@test "regresion traversal_manifest" {
  run python3 "$RAIZ/tests/regression.py" traversal_manifest
  [ "$status" -eq 0 ]
}

@test "regresion corruption" {
  run python3 "$RAIZ/tests/regression.py" corruption
  [ "$status" -eq 0 ]
}

@test "regresion missing_identity" {
  run python3 "$RAIZ/tests/regression.py" missing_identity
  [ "$status" -eq 0 ]
}

@test "regresion wrong_identity" {
  run python3 "$RAIZ/tests/regression.py" wrong_identity
  [ "$status" -eq 0 ]
}

@test "regresion bad_cipher" {
  run python3 "$RAIZ/tests/regression.py" bad_cipher
  [ "$status" -eq 0 ]
}

@test "regresion tar_traversal" {
  run python3 "$RAIZ/tests/regression.py" tar_traversal
  [ "$status" -eq 0 ]
}

@test "regresion tar_absolute" {
  run python3 "$RAIZ/tests/regression.py" tar_absolute
  [ "$status" -eq 0 ]
}

@test "regresion tar_symlink" {
  run python3 "$RAIZ/tests/regression.py" tar_symlink
  [ "$status" -eq 0 ]
}

@test "regresion tar_duplicate" {
  run python3 "$RAIZ/tests/regression.py" tar_duplicate
  [ "$status" -eq 0 ]
}

@test "regresion tar_truncated" {
  run python3 "$RAIZ/tests/regression.py" tar_truncated
  [ "$status" -eq 0 ]
}

@test "regresion restore_bytes" {
  run python3 "$RAIZ/tests/regression.py" restore_bytes
  [ "$status" -eq 0 ]
}

@test "regresion nonempty_db" {
  run python3 "$RAIZ/tests/regression.py" nonempty_db
  [ "$status" -eq 0 ]
}

@test "regresion audit_failure" {
  run python3 "$RAIZ/tests/regression.py" audit_failure
  [ "$status" -eq 0 ]
}
