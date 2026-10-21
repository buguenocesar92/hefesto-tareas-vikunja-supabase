#!/usr/bin/env bats
load 'ayudante'

setup() {
  preparar_kit
  preparar_datos
}

@test "contrato: el informe no se escribe sobre un enlace simbolico" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    InformeSinSymlink.test_rechaza_escribir_sobre_enlace_simbolico
  [ "$status" -eq 0 ]
}

@test "contrato: el informe se escribe con permisos restringidos" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    InformeSinSymlink.test_escribe_informe_regular_con_permisos_restringidos
  [ "$status" -eq 0 ]
}

@test "contrato: env.vars ignora las continuaciones de clave PEM" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    NombresEnv.test_ignora_continuaciones_de_clave_pem
  [ "$status" -eq 0 ]
}

@test "contrato: env.vars ignora un fragmento base64 suelto" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    NombresEnv.test_ignora_fragmento_base64_suelto
  [ "$status" -eq 0 ]
}

@test "contrato: env.vars conserva un nombre largo convencional" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    NombresEnv.test_conserva_nombre_largo_convencional
  [ "$status" -eq 0 ]
}

@test "contrato: env.vars ignora comentarios y lineas sin asignacion" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    NombresEnv.test_ignora_comentarios_y_lineas_sin_asignacion
  [ "$status" -eq 0 ]
}

@test "contrato: el manifiesto tiene que declarar los artefactos obligatorios" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    ArtefactosObligatorios.test_exige_declarar_los_artefactos_obligatorios
  [ "$status" -eq 0 ]
}

@test "contrato: un conjunto de artefactos declarado se acepta" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    ArtefactosObligatorios.test_acepta_el_conjunto_declarado
  [ "$status" -eq 0 ]
}

@test "contrato: sin artefactos obligatorios no se comprueba" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    ArtefactosObligatorios.test_sin_artefactos_obligatorios_no_se_comprueba
  [ "$status" -eq 0 ]
}

@test "contrato: falta el artefacto y no se declara la exclusion" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    ArtefactosObligatorios.test_ejecutar_check_exige_declarar_la_exclusion
  [ "$status" -eq 0 ]
}

@test "contrato: la exclusion declarada se acepta" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    ArtefactosObligatorios.test_ejecutar_check_acepta_exclusion_declarada
  [ "$status" -eq 0 ]
}

@test "contrato: un artefacto vacio se rechaza" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    ArtefactosObligatorios.test_ejecutar_check_rechaza_artefacto_vacio
  [ "$status" -eq 0 ]
}

@test "contrato: el tar con entradas duplicadas se rechaza" {
  run python3 "$RAIZ/tests/contrato_test.py" \
    TarHostil.test_rechaza_entradas_duplicadas
  [ "$status" -eq 0 ]
}

@test "contrato: el tar con ruta absoluta se rechaza" {
  run python3 "$RAIZ/tests/contrato_test.py" TarHostil.test_rechaza_ruta_absoluta
  [ "$status" -eq 0 ]
}

@test "contrato: el tar con traversal se rechaza" {
  run python3 "$RAIZ/tests/contrato_test.py" TarHostil.test_rechaza_traversal
  [ "$status" -eq 0 ]
}

@test "contrato: el tar con enlace simbolico se rechaza" {
  run python3 "$RAIZ/tests/contrato_test.py" TarHostil.test_rechaza_enlace_simbolico
  [ "$status" -eq 0 ]
}

@test "contrato: un archivo ilegible se rechaza" {
  run python3 "$RAIZ/tests/contrato_test.py" TarHostil.test_rechaza_archivo_ilegible
  [ "$status" -eq 0 ]
}

@test "contrato: un tar limpio se acepta" {
  run python3 "$RAIZ/tests/contrato_test.py" TarHostil.test_acepta_tar_limpio
  [ "$status" -eq 0 ]
}
