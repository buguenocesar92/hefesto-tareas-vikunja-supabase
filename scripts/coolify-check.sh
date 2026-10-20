#!/usr/bin/env bash
# coolify-check.sh: valida que el compose del kit cumple el contrato de Coolify.
# Uso: bash scripts/coolify-check.sh
# Sale 0 si el compose cumple, 1 en caso contrario.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$RAIZ/compose.yaml"
BD_TIPO="supabase-pg"

# Ficticios no secretos (regla del contrato: nada secreto en el compose de Coolify).
DUMMY='x1234567890abcdef'
DB_DUMMY='db.ejemplo.invalid'
URL_DUMMY='https://ejemplo.invalid'

error() { printf 'error: %s\n' "$*" >&2; }
ok()   { printf 'ok: %s\n' "$*"; }

# Extrae todas las variables ${VAR}, ${VAR:-defecto} y ${VAR:?msg} del compose.
extraer_vars() {
    grep -oE '\$\{[A-Z_][A-Z0-9_]*(:[?][^}]*|:[-][^}]*)?\}' "$1" \
        | sed -E 's/^\$\{//; s/\}$//; s/:.*$//' \
        | sort -u
}

# Escribe un .env temporal con valores ficticios por cada ${VAR} del compose.
escribir_env() {
    local destino="$1"
    : > "$destino"
    while IFS= read -r var; do
        [ -z "$var" ] && continue
        case "$var" in
            PUBLIC_URL)        printf "PUBLIC_URL=%s\n" "$URL_DUMMY" >> "$destino" ;;
            DB_HOST)           printf "DB_HOST=%s\n" "$DB_DUMMY" >> "$destino" ;;
            SERVICE_SECRET)    printf "SERVICE_SECRET=%s\n" "$DUMMY" >> "$destino" ;;
            *)                 printf "%s=%s\n" "$var" "$DUMMY" >> "$destino" ;;
        esac
    done < <(extraer_vars "$COMPOSE")
    # El despliegue real exige estas dos en true (contrato: base dedicada y sin PostgREST).
    printf "SUPABASE_DEDICATED_CONFIRMED=true\n" >> "$destino"
    printf "SUPABASE_DATA_API_DISABLED=true\n" >> "$destino"
    # Para supabase-pg el chequeo exige ver DB_NAME=mvp_prueba y DB_SSLMODE=disable.
    if [ "$BD_TIPO" = "supabase-pg" ]; then
        {
            printf "DB_NAME=mvp_prueba\n"
            printf "DB_SSLMODE=disable\n"
            printf "DB_USER=%s\n" "$DUMMY"
        } >> "$destino"
    fi
}

# Falla si algún servicio sin profiles expone puertos, container_name o capabilities.
revisar_sin_profiles() {
    local renderizado="$1"
    jq -e -r '
        .services
        | to_entries[]
        | select(((.value.profiles // []) | length) == 0)
        | .key as $svc
        | .value
        | [
            (if ((.ports // []) | length) > 0 then "\($svc): publica puertos" else empty end),
            (if (.container_name // null) != null then "\($svc): container_name fijo" else empty end),
            (if (.privileged // false) == true then "\($svc): privileged" else empty end),
            (if ((.cap_add // []) | length) > 0 then "\($svc): cap_add" else empty end),
            (if ((.devices // []) | length) > 0 then "\($svc): devices" else empty end),
            (if (.network_mode // null) == "host" then "\($svc): network_mode host" else empty end),
            (if (.pid // null) == "host" then "\($svc): pid host" else empty end),
            (if (.ipc // null) == "host" then "\($svc): ipc host" else empty end),
            (if ((.security_opt // []) | map(select(test("unconfined"))) | length) > 0
                then "\($svc): security_opt unconfined" else empty end)
          ]
        | select(length > 0)[]
    ' <<<"$renderizado"
}

# Falla si algún bind monta rutas fuera del repo o el socket de Docker.
revisar_binds() {
    local renderizado="$1"
    local repo="$2"
    local origen_abs servicio
    while IFS=$'\t' read -r origen servicio; do
        [ -z "$origen" ] && continue
        if [ "$origen" = "/var/run/docker.sock" ]; then
            error "$servicio: bind de docker.sock prohibido"
            return 1
        fi
        # docker compose config ya normaliza a absoluto, pero defendemos contra
        # rutas relativas que escalen con .. y se salgan del repo.
        origen_abs="$(realpath -m -- "$origen" 2>/dev/null || printf '%s' "$origen")"
        if [ "$origen_abs" != "$repo" ] && [[ "$origen_abs" != "$repo"/* ]]; then
            error "$servicio: bind fuera del repo: $origen_abs"
            return 1
        fi
    done < <(jq -r '
        .services
        | to_entries[]
        | select(((.value.profiles // []) | length) == 0)
        | .key as $svc
        | ((.value.volumes // [])[]? | select(type == "object"))
        | "\(.source)\t\($svc)"
    ' <<<"$renderizado")
}

# Para supabase-pg: el DSN del servicio web debe respetar DB_NAME y DB_SSLMODE
# que el compose recibio por entorno. Comprobamos por campos, no por substring.
revisar_parametros_pg() {
    local renderizado="$1"
    # DB_NAME: el campo DATABASE del DSN (vikunja lo nombra VIKUNJA_DATABASE_DATABASE).
    if ! jq -e '
        [.. | objects | select(has("VIKUNJA_DATABASE_DATABASE")).VIKUNJA_DATABASE_DATABASE]
        | any(. == "mvp_prueba")
    ' <<<"$renderizado" >/dev/null; then
        error "DB_NAME=mvp_prueba no llega al DSN del servicio web"
        return 1
    fi
    # DB_SSLMODE: el campo sslmode del DSN (vikunja lo nombra VIKUNJA_DATABASE_SSLMODE).
    if ! jq -e '
        [.. | objects | select(has("VIKUNJA_DATABASE_SSLMODE")).VIKUNJA_DATABASE_SSLMODE]
        | any(. == "disable")
    ' <<<"$renderizado" >/dev/null; then
        error "DB_SSLMODE=disable no llega al DSN del servicio web"
        return 1
    fi
}

principal() {
    if ! command -v docker >/dev/null 2>&1; then
        error "docker no esta instalado"; exit 1
    fi
    if ! command -v jq >/dev/null 2>&1; then
        error "jq no esta instalado"; exit 1
    fi

    tmp="$(mktemp "${TMPDIR:-/tmp}/coolify-check.XXXXXX")"
    # La trap de EXIT sobrevive a la salida de principal(); tmp debe ser global.

    escribir_env "$tmp"

    local renderizado
    # docker compose emite WARNING a stderr (config.json del daemon). Los descartamos.
    if ! renderizado="$(docker compose --project-directory "$RAIZ" \
            -f "$COMPOSE" --env-file "$tmp" config --format json 2>/dev/null)"; then
        # Si fallo, mostramos el error completo para diagnosticar.
        docker compose --project-directory "$RAIZ" \
            -f "$COMPOSE" --env-file "$tmp" config --format json >&2 || true
        error "compose no pudo renderizar con el .env ficticio"
        exit 1
    fi

    # revisar_sin_profiles devuelve 0 con violaciones o 1 sin ellas; lo que importa es el texto.
    local violations=()
    # shellcheck disable=SC2207 # array intencional; las lineas no contienen globs.
    if violations=($(revisar_sin_profiles "$renderizado" 2>/dev/null || true)); then
        :
    fi
    if [ "${#violations[@]}" -gt 0 ]; then
        printf '%s\n' "${violations[@]}" >&2
        error "compose expone superficies prohibidas por Traefik/Coolify"
        exit 1
    fi

    if ! revisar_binds "$renderizado" "$RAIZ"; then
        exit 1
    fi

    if [ "$BD_TIPO" = "supabase-pg" ]; then
        if ! revisar_parametros_pg "$renderizado"; then
            exit 1
        fi
    fi

    ok "compose cumple el contrato Coolify ($BD_TIPO)"
}

principal "$@"