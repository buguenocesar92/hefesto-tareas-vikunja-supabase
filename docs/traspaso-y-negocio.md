# Oferta y traspaso
Servicio propuesto: implementación inicial, configuración de proyectos/equipos, capacitación, alojamiento administrado, respaldos supervisados y soporte mensual. Cotice según usuarios, espacio, frecuencia de copia y tiempo de atención; no hay precios ni SLA comprometidos en este paquete.

Vikunja es apropiado para tareas y coordinación ligera. Para planificación avanzada use el kit OpenProject; para unificar ventas, facturación y proyectos evalúe Odoo. No es un reemplazo de ERP ni emite documentos tributarios.

## Traspaso a otro operador
Entregar inventario de dominio/DNS/proxy, cuenta de alojamiento, proyecto Supabase y rol, versión/digest, volumen, respaldo verificado, retención, responsables y acta de aceptación. Transferir secretos por canal seguro y rotar accesos del operador saliente. Conservar créditos y cumplir AGPL-3.0 de Vikunja; el ZIP distribuye configuración, no su binario.

## Traspaso hacia Odoo
Es un proyecto de migración funcional, no una conexión instalada. Extraer mediante exportación/API nativa de la versión instalada y adaptar al importador/API de la versión Odoo elegida.

| Origen | Destino conceptual Odoo | Validación |
|---|---|---|
| Proyecto | project.project | Nombre y cliente |
| Tarea | project.task | Título, descripción y proyecto |
| Responsable | res.users | Correspondencia por correo, no por ID |
| Estado/bucket | Etapa de tarea | Mapeo acordado y orden |
| Fecha límite | Fecha límite | Zona horaria y campo de versión |
| Comentarios y archivos | Mensajes/adjuntos | Importación específica y autoría |
| Etiquetas | Etiquetas | Duplicados y nomenclatura |

Mantener tabla de IDs origen/destino para reintentos, probar una muestra, congelar escrituras durante corte, reconciliar conteos y adjuntos, mantener origen de solo consulta hasta la aceptación. Contraseñas y tokens no se migran. No se incluyen automatizaciones Odoo/n8n ni importadores CSV ficticios.

## Plantilla operativa para crear manualmente
Proyecto «Implementación cliente»: Diagnóstico → Configuración → Pruebas → Entrega. Columnas: Pendiente / En curso / Revisión / Hecho. Tareas: recopilar accesos, cargar información, probar permisos, demostrar restauración, capacitar y obtener aceptación. Esta plantilla es una guía, no datos instalados.
