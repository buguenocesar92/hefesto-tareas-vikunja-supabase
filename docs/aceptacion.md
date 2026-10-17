# Aceptación pendiente en infraestructura real
- [ ] Preflight: conexión TLS válida; falla con CA incorrecta; rol vikunja_app sin privilegios administrativos.
- [ ] Arranque/migraciones completan en PostgreSQL destino; registrar versiones exactas de servidor e imágenes.
- [ ] Crear dos cuentas por CLI, iniciar sesión y verificar registro público cerrado.
- [ ] Crear proyecto, tarea, responsable, fecha y columna Kanban; mover y completar tarea.
- [ ] Adjuntar y descargar archivo; reiniciar app y verificar persistencia.
- [ ] Compartir solo proyecto elegido y comprobar que la otra cuenta no accede a proyectos privados.
- [ ] HTTPS y URL pública correctos; no hay puerto bootstrap expuesto al exterior.
- [ ] Correo desactivado sin prometer recordatorios ni recuperación por email.
- [ ] Respaldo y restauración completos en otro proyecto; cotejar tareas y hashes de adjuntos.
- [ ] Registrar responsable, retención, RPO/RTO medidos y aceptación del cliente.

Revisión realizada al preparar el kit: sintaxis Python/shell, estructura YAML, parámetros contra código upstream 2.7.0, generación de secretos y archivo ZIP. No se ejecutó Docker, PostgreSQL, Coolify ni un navegador contra una instancia real. Los checks anteriores permanecen pendientes.
