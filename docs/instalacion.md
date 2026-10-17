# Instalación
1. Cree un proyecto Supabase exclusivo PostgreSQL 16 o 17. Desactive Data API desde sus ajustes. No reutilice una base de otras aplicaciones.
2. Ejecute sql/01-supabase-app.sql en SQL Editor con el propietario. Genere .env con `python3 scripts/configure.py`. Asigne el valor DB_PASSWORD al rol con `\password vikunja_app` en una sesión psql administrativa; no coloque contraseñas en comandos compartidos.
3. Copie el certificado CA en certs/ca.crt. En .env edite DB_HOST, DB_USER y PUBLIC_URL con barra final. Use conexión directa puerto 5432; requiere IPv6 o complemento IPv4. Alternativa: Session pooler 5432, con host exacto del panel y usuario `vikunja_app.REFERENCIA`. Nunca Transaction pooler 6543. Para migraciones y respaldo prefiera conexión directa y valide conectividad desde el servidor.
4. Confirme SUPABASE_DEDICATED_CONFIRMED y SUPABASE_DATA_API_DISABLED como true solo después de realizarlo. Los flags son declaraciones del operador; el script verifica permisos, no la configuración del panel.
5. Ejecute `docker compose config --quiet` y `docker compose run --rm preflight`. No imprima el Compose completo en tickets: contiene secretos interpolados.
6. Ejecute `docker compose up -d app`. El arranque nativo realiza migraciones; revise `docker compose logs --tail=100 app`. No interrumpa una migración. No hay migración ni carga previa en este ZIP.
7. Cree cada cuenta mediante `docker compose exec app /app/vikunja/vikunja user create --username propietario --email propietario@su-dominio.cl`. Omita --password: la CLI la solicita. Consulte `user --help` para mantenimiento. Las cuentas no se comparten entre clientes.
8. En Coolify use Compose desde el repositorio o directorio completo, configure variables secretas, monte certs y ops conservando sus rutas y asigne dominio HTTPS al servicio app, puerto interno 3456. El proxy debe enviar Host y X-Forwarded-Proto. No publique puertos de base de datos. Valide que Coolify conserva depends_on y espera los servicios de preparación.
9. Abra el dominio, seleccione español en ajustes, cree un proyecto y pruebe docs/aceptacion.md antes de entregar.

## Prueba privada sin dominio
`docker compose -f compose.yaml -f compose.bootstrap.yaml up -d app`
En su equipo abra túnel `ssh -L 8095:127.0.0.1:8095 usuario@servidor` y visite http://localhost:8095/. Cree el usuario por CLI como arriba. Al pasar a producción quite el override y ejecute `docker compose up -d --force-recreate app`; confirme que 8095 ya no esté publicado.

## Correo y acceso
Este paquete no envía correo. Recuperación por correo y recordatorios requieren configurar SMTP nativo (mailer.*), credenciales y pruebas de entrega. Mientras tanto, la recuperación es administrativa por CLI. No habilite registro público para crear usuarios; use la CLI. Los proyectos y equipos se comparten mediante permisos propios de Vikunja.

## Separación por cliente
Una instalación, proyecto Supabase, volumen y secreto por cliente. En un mismo host use nombres de proyecto Compose distintos con `COMPOSE_PROJECT_NAME` en .env (prevalece sobre name) y VOLUME_PREFIX único; conserve ambos en todos los comandos y respaldos. Sincronizar la instalación desde otro panel requiere llevar las mismas variables y nombres de volumen.
