# Contrato de respaldo y restauracion de Hefesto Studio

Este documento es **normativo** para el kit `hefesto-tareas`. Los kits que no lo
cumplan quedan fuera del flujo orquestado: el mismo documento esta en
`hefesto-monitor-uptime-kuma` (el que produce el respaldo) y en
`hefesto-respaldo-kopia` (el que lo almacena), para que ambos extremos hablen el
mismo idioma.

## 1. Las reglas

1. **Nombre del script de respaldo**: `scripts/backup.py` (Python) o
   `scripts/respaldar.sh` (Bash). Los dos extremos se reconocen por el
   contenido del respaldo, no por el nombre.
2. **Salida en `<timestamp>/`** con, como minimo:
   - el dump de la base de datos y/o los tar de los volumenes con material
     personal, **cifrados con `age`**;
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
   donde aterriza el respaldo. `env.vars` solo lleva **nombres de variable
   validos**: una linea de continuacion (un valor multilinea entre comillas) no
   es una variable y no puede aparecer ahi, porque filtraria parte del secreto.
6. **El dump de la base y el material personal (volumenes de archivos) solo
   viajan cifrados con `age`** (`public.dump.age` y `files.tar.gz.age`). Sus
   versiones en claro (`public.dump` y `files.tar.gz`) estan en la lista de
   prohibidos de `scripts/check_backup.py` y el respaldo se rechaza con codigo
   4 si aparecen. Los permisos restrictivos no son cifrado.
7. **El manifiesto declara el contenido del respaldo**: siempre los artefactos
   obligatorios (`env.vars`) y, para cada artefacto opcional, o su presencia o
   su exclusion explicita en la lista `excluidos`. Un manifiesto que solo
   declara `env.vars` no es un respaldo verificable y se rechaza con codigo 2.
8. **Existe un script de restauracion** que valida, en este orden: el
   `manifest.json` (version y `status`), el checksum, los artefactos
   obligatorios y las exclusiones declaradas, las rutas dentro del tar (nada
   absoluto, nada con `..`, nada duplicado, nada que no sea archivo o directorio)
   y que el **volumen destino este vacio**. El preflight se completa **antes**
   de tocar la base o los volumenes: si el preflight falla, no se escribe nada.
   Nunca vacia ni sobrescribe datos existentes.
9. **La restauracion es explicita**: sin `--confirmar CONFIRMAR_RESTAURACION`
   no se escribe nada (codigo 3); `--dry-run` simula y no escribe.
10. **El informe de restauracion (`restore-report.json`) nunca se escribe
    siguiendo un enlace simbolico**: un enlace en el respaldo permitiria
    sobrescribir cualquier fichero del sistema sin alterar los checksums.
11. **Existe una prueba bats** que ejercita el ciclo completo con **datos
    sinteticos** y en aislamiento: ningun contenedor real, ningun volumen real.
12. **Existe un `.env.example` sin secretos** que documenta todas las variables
    que el compose exige.
13. **`gitleaks` corre en CI** sobre el repositorio y sobre el historial.
14. **El compose fija la imagen por digest**, no por etiqueta: una etiqueta
    puede cambiar de contenido sin que nadie lo note.
15. **El estado de despliegue no viaja en el repositorio**: los identificadores
    (uuid de la app, url publica, fechas) viven en un archivo de estado con
    permisos restrictivos, fuera del control de versiones.
16. **Cada restauracion deja rastro de auditoria**: origen, sha256 verificado,
    destino y resultado, en un log append-only (`logs/restore.log`). Sin
    valores de secretos: solo nombres y hashes. Tambien quedan registrados los
    intentos fallidos.

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

## 3. Por que el dump tambien viaja cifrado

El dump de la base contiene cuentas, correos y hashes de contrasena. Un
respaldo vive en el disco, se copia a otro equipo y sube a un bucket: si el
dump viaja en claro, cada copia es una copia de los datos personales de los
titulares (Ley 21.719).

Por eso el dump se cifra con el mismo receptor age que el volumen de
contenido. El dump se produce directamente en el cifrador: **el texto plano
nunca se escribe en disco**. Sin receptor age, el dump no viaja y el
manifiesto lo declara en `excluidos`; el respaldo sale sin el y el operador
tiene que(configurar `AGE_RECIPIENT` (o `SOPS_AGE_RECIPIENT`) para tener una
copia de la base.

## 4. El receptor `age`: quien custodia la clave

La clave publica del receptor es un **insumo externo**. La privada vive en el
gestor de secretos del cliente (Infisical, Vaultwarden) o, si el cliente no
tiene, en un sobre cifrado fuera del servidor. El kit que respalda solo usa
la publica.

Consecuencias que hay que aceptar antes de cifrar:

- **Perder la clave privada implica regenerar los secretos y volver a
  desplegar.** Los despliegues anteriores quedan inservibles.
- **Rotar la clave obliga a volver a cifrar**: los respaldos viejos siguen
  ligados a la clave con que se hicieron.

## 5. Migrar respaldos que ya existen

Los respaldos hechos antes de este contrato **no se tocan**. La migracion es
manual, archivo por archivo, y nunca borra el original:

1. Cifrar con la clave del receptor **al lado** del original (`<archivo>.enc`).
2. Verificar que el descifrado devuelve el original byte a byte.
3. Recien entonces, borrar el original a mano.

Un respaldo viejo sin cifrar es un riesgo asumido y conocido: esta en el punto
5 del contrato como deuda.

## 6. Como se verifica el contrato

```bash
bats tests/                      # la suite del kit que respalda
bats tests/backup_restore.bats   # el ciclo con datos sinteticos
python3 scripts/check_backup.py /ruta/respaldo   # 0 / 2 / 4
```

Un kit que no tiene ninguna de las dos pruebas no se considera productionizado.
