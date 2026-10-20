#!/bin/sh
set -eu
[ "$SUPABASE_DEDICATED_CONFIRMED" = true ] || { echo 'Confirme proyecto Supabase exclusivo'; exit 1; }
[ "$SUPABASE_DATA_API_DISABLED" = true ] || { echo 'Desactive Data API y confirme variable'; exit 1; }
# sslmode parametrizable, pero solo valores reconocidos por libpq. Si llega algo
# distinto abortamos para no abrir un fail-open silencioso (typo, valor invalido).
case "${PGSSLMODE:-verify-full}" in
    disable|allow|prefer|require|verify-ca|verify-full) ;;
    *) echo "DB_SSLMODE invalido: ${PGSSLMODE:-verify-full}"; exit 1 ;;
esac
# El certificado CA solo es obligatorio con sslmode=verify-full; con sslmode=disable
# el cliente negocia TLS sin verificar cadena (uso tipico: Postgres del mismo docker network).
if [ "${PGSSLMODE:-verify-full}" = verify-full ]; then
    [ -s "$PGSSLROOTCERT" ] || { echo 'Falta certificado CA'; exit 1; }
fi
export PGCONNECT_TIMEOUT=15
psql --no-psqlrc -v ON_ERROR_STOP=1 -f /opt/hefesto/preflight.sql