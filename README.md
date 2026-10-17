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
