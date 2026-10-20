# Hefesto Tareas — Vikunja + Supabase
Kit de instalación nativa de Vikunja 2.7.0 para equipos pequeños: proyectos, tareas, Kanban, responsables, fechas y adjuntos. Código de despliegue, SQL y operaciones; no es una aplicación ya desplegada ni una copia visual.

## Qué incluye
- Docker Compose para Coolify/VPS, imagen Vikunja fijada por digest.
- Supabase PostgreSQL dedicado (16/17), rol propio y TLS verify-full.
- Registro público, enlaces públicos y correo desactivados inicialmente.
- Archivos persistentes, respaldo coordinado con la app detenida y restauración en destino vacío.
- Guías de puesta en marcha, aceptación y traspaso a otro servidor u Odoo.

Empiece por docs/instalacion.md. Requisitos: Docker Engine, Compose v2, Python 3.11+, dominio HTTPS, proyecto Supabase dedicado y acceso al servidor. El ZIP no contiene credenciales, binarios ni datos de clientes.

**Estado:** configuración y scripts revisados estáticamente. Falta ejecutar la instalación y probar flujos y recuperación en infraestructura real. No se promete compatibilidad de producción sin esa aceptación.

Supabase aporta la base PostgreSQL. Usuarios y permisos los administra Vikunja; este kit no integra Supabase Auth, Storage, Realtime ni claves anon/service_role.

## Despliegue en Coolify (MVP Hefesto)

Variables adicionales reconocidas por el compose y `ops/preflight.sh`:

- `DB_NAME` (por defecto `postgres`): nombre de la base en el Postgres dedicado.
  Coolify crea su propia base por aplicación (`mvp_<slug>`); el compose la propaga
  al DSN de Vikunja y al bloque `x-pg`.
- `DB_SSLMODE` (por defecto `verify-full`): modo TLS del cliente.
  Si se cambia a `disable` (uso típico: Postgres del mismo docker network,
  sin CA disponible), `preflight.sh` deja de exigir `certs/ca.crt` y el DSN
  sigue funcionando sin `sslrootcert`.
- `DB_USER` (por defecto `vikunja_app`) ya era parametrizable.
- `SUPABASE_DEDICATED_CONFIRMED=true` y `SUPABASE_DATA_API_DISABLED=true`
  siguen siendo obligatorios: la base es exclusiva y no expone PostgREST.

El script `scripts/coolify-check.sh` verifica que `compose.yaml` cumpla el
contrato (sin puertos ni capacidades indebidas, con `DB_NAME` y `DB_SSLMODE`
parametrizables) antes de subir el cambio. Úselo en CI y localmente:

```bash
bash scripts/coolify-check.sh
```
