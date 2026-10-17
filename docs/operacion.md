# Respaldo y recuperación
Ejecute `python3 scripts/backup.py` desde un host con Docker. Detiene app durante dump+archivos y la reinicia si estaba activa. Impida operaciones CLI, cambios externos en SQL y despliegues concurrentes durante el respaldo. Un directorio sin manifest completed es incompleto. El backup incluye .env y por tanto claves; almacénelo cifrado, fuera del servidor, con acceso restringido. Los hashes detectan daños, no sustituyen autenticación/cifrado.

Puede programar ese comando con el planificador del servidor, registrando éxito y alertas. No se ha instalado una tarea automática. Defina retención y pruebe recuperación periódica según necesidades del cliente.

## Restauración en destino nuevo
1. Mantenga detenida la app destino. Prepare otro proyecto Supabase vacío y rol/CA siguiendo instalación. Use la misma versión 2.7.0 y un VOLUME_PREFIX nuevo; no ejecute app todavía.
2. Cree .env destino con host/clave nuevos. Recupere SERVICE_SECRET del .env respaldado; no copie ciegamente el host antiguo. Conserve el respaldo original y su manifiesto intactos.
3. Ejecute `docker compose run --rm preflight`.
4. `python3 scripts/restore_db.py /ruta/respaldo`
5. `python3 scripts/restore_files.py /ruta/respaldo`
6. `docker compose up -d app` y complete aceptación. Cambie DNS solo después de verificar usuarios, tareas, adjuntos y permisos.

La restauración rechaza una base o volumen con contenido. No borra ni fusiona instalaciones existentes. Si falla parcialmente, no reintente sobre el destino parcialmente poblado: investigue y prepare otro destino vacío. Nunca borre el origen para reintentar. La app debe estar detenida también si se administra con otro proyecto Compose o panel.

Se respalda solo public y el volumen de archivos; no incluye Supabase Auth/Storage ni todo el proyecto Supabase. Conserve también este ZIP, certificado CA vigente y configuración de proxy/DNS. No use pg_dump como migración directa a la base de Odoo.

## Actualizaciones
La app está fijada por digest. Las herramientas usan postgres:17-alpine y pueden recibir parches; para congelarlas, registre su digest validado en el servidor. Antes de actualizar: respaldo, copia de ensayo, revisión de cambios y pruebas. Una vez migrado el esquema, bajar solo la imagen no garantiza reversión: restaure DB+archivos del respaldo en destino nuevo.

## Supervisión
Compruebe HTTPS, inicio de sesión y capacidad de guardar tareas. No se añade un healthcheck con curl/wget: la imagen oficial es scratch y no contiene shell. Configure una comprobación HTTP externa en Coolify y alertas de disco, DB y backups. Adjuntos viven en /app/vikunja/files, UID 1000. No añada varias réplicas sin diseñar almacenamiento y concurrencia.
