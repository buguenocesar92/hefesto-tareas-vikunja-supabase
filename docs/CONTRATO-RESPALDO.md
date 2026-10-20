# Contrato de respaldo y restauracion de Hefesto Studio

Este documento es **normativo** para el kit `hefesto-tareas`. Los kits que no lo
cumplan quedan fuera del flujo orquestado: el mismo documento esta en
`hefesto-monitor-uptime-kuma` (el que produce el respaldo) y en
`hefesto-respaldo-kopia` (el que lo almacena), para que ambos extremos hablen
el mismo idioma.

## 1. Las reglas

1. **Nombre del script de respaldo**: `scripts/backup.py` (Python) o
   `scripts/respaldar.sh` (Bash). Los dos extremos se reconocen por el
   contenido del respaldo, no por el nombre.
2. **Salida en `<timestamp>/`** con, como minimo:
   - el dump de la base de datos y/o los tar de los volumenes con material
     personal;
   - `env.vars`: los nombres de las variables del `.env`, sin valores;
   - `manifest.json`: la metadata del respaldo.
3. **`manifest.json` contiene SIEMPRE** estas claves: `software`, `version`,
   `database`, `sha256`, `status`. Un respaldo sin las cinco no es un respaldo
   del flujo orquestado.
4. **`status` solo vale `completed`** si el proceso termino sin error. Cualquier
   otro valor significa que el respaldo **no se restaura**: la restauracion
   aborta antes de tocar el destino.
5. **El `.env` NUNCA se copia en claro.** Se documenta su ausencia en el
   manifiesto o se cifra con `age` usando la clave publica del receptor. Un
   `.env` en claro dentro de un respaldo es una credencial tendida en el disco
   donde aterriza el respaldo.
6. **El material personal (volumenes de archivos) solo viaja cifrado con
   `age`** (`files.tar.gz.age`). Su version en claro esta en la lista de
   prohibidos de `scripts/check_backup.py` y el respaldo se rechaza con codigo
   4 si aparece.
7. **Existe un script de restauracion** que valida, en este orden: el
   `manifest.json` (version y `status`), el checksum, las rutas dentro del tar
   (nada absoluto, nada con `..`, nada que no sea archivo o directorio) y que el
   **volumen destino este vacio**. Nunca vacia ni sobrescribe datos existentes.
8. **La restauracion es explicita**: sin `--confirmar CONFIRMAR_RESTAURACION`
   no se escribe nada (codigo 3); `--dry-run` simula y no escribe.
9. **Existe una prueba bats** que ejercita el ciclo completo con **datos
   sinteticos** y en aislamiento: ningun contenedor real, ningun volumen real.
10. **Existe un `.env.example` sin secretos** que documenta todas las variables
    que el compose exige.
11. **`gitleaks` corre en CI** sobre el repositorio y sobre el historial.
12. **El compose fija la imagen por digest**, no por etiqueta: una etiqueta
    puede cambiar de contenido sin que nadie lo note.
13. **El estado de despliegue no viaja en el repositorio**: los identificadores
    (uuid de la app, url publica, fechas) viven en un archivo de estado con
    permisos restrictivos, fuera del control de versiones.
14. **Cada restauracion deja rastro de auditoria**: origen, sha256 verificado,
    destino y resultado, en un log append-only (`logs/restore.log`). Sin
    valores de secretos: solo nombres y hashes.

## 2. Por que el `.env` no se copia en claro

El `.env` es lo que se lleva el acceso a la base de datos, al SMTP y a las
claves de servicio. Un respaldo vive en el disco, se copia a otro equipo, se
sube a un bucket y a veces termina en un ticket de soporte. Si el `.env` viaja
en claro, cada copia del respaldo es una copia de las credenciales.

Lo que si puede viajar, y asi viaja:

- **Los nombres de las variables** (`env.vars`): sin valores, para saber que
  hay que rellenar en el destino.
- **El `.env` cifrado** (`env.age`), si hay un receptor age configurado.

Si no hay receptor age, el respaldo sale **sin** el `.env` y el manifiesto lo
dice. No hay modo degradado a texto plano.

## 3. El receptor `age`: quien custodia la clave

La clave publica del receptor es un **insumo externo**. La privada vive en el
gestor de secretos del cliente (Infisical, Vaultwarden) o, si el cliente no
tiene, en un sobre cifrado fuera del servidor. El kit que respalda solo usa
la publica.

Consecuencias que hay que aceptar antes de cifrar:

- **Perder la clave privada implica regenerar los secretos y volver a
  desplegar.** Los despliegues anteriores quedan inservibles.
- **Rotar la clave obliga a volver a cifrar**: los respaldos viejos siguen
  ligados a la clave con que se hicieron.

## 4. Migrar respaldos que ya existen

Los respaldos hechos antes de este contrato **no se tocan**. La migracion es
manual, archivo por archivo, y nunca borra el original:

1. Cifrar con la clave del receptor **al lado** del original (`<archivo>.enc`).
2. Verificar que el descifrado devuelve el original byte a byte.
3. Recien entonces, borrar el original a mano.

Un respaldo viejo sin cifrar es un riesgo asumido y conocido: esta en el punto
5 del contrato como deuda.

## 5. Como se verifica el contrato

```bash
bats tests/                      # la suite del kit que respalda
bats tests/backup_restore.bats   # el ciclo con datos sinteticos
python3 scripts/check_backup.py /ruta/respaldo   # 0 / 2 / 4
```

Un kit que no tiene ninguna de las dos pruebas no se considera productionizado.
