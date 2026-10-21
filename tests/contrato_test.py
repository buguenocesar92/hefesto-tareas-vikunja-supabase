#!/usr/bin/env python3
"""Pruebas unitarias del contrato de respaldo (tests/contrato_test.py).

Solo datos sinteticos: nunca un .env real ni datos de personas. Cada prueba
comprueba una garantia del contrato de docs/CONTRATO-RESPALDO.md.
"""
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import respaldo_contrato as contrato  # noqa: E402

# Receptor age ficticio: la prueba no cifra nada, solo comprueba que el
# destino enlazado se rechaza antes de tocar el fichero de destino.
RECEPTOR_FICTICIO = "age1" + "q" * 58


class InformeSinSymlink(unittest.TestCase):
    """El informe de restauracion nunca se escribe siguiendo un enlace."""

    def test_rechaza_escribir_sobre_enlace_simbolico(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            victima = base / "victima.txt"
            victima.write_text("contenido original\n", encoding="utf-8")
            (base / "restore-report.json").symlink_to(victima)
            with self.assertRaises(contrato.RespaldoError) as ctx:
                contrato.escribir_informe(base, software="kit", resultado="restaurado")
            self.assertEqual(ctx.exception.codigo, 2)
            self.assertEqual(victima.read_text(encoding="utf-8"), "contenido original\n")

    def test_escribe_informe_regular_con_permisos_restringidos(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            informe = contrato.escribir_informe(base, software="kit", resultado="restaurado")
            destino = base / "restore-report.json"
            self.assertFalse(destino.is_symlink())
            self.assertTrue(destino.is_file())
            self.assertEqual(oct(destino.stat().st_mode & 0o777), oct(0o600))
            self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["resultado"],
                             "restaurado")
            self.assertEqual(informe["resultado"], "restaurado")


class NombresEnv(unittest.TestCase):
    """env.vars solo lleva nombres de variable: nunca fragmentos de secretos."""

    def test_ignora_continuaciones_de_clave_pem(self):
        # El encabezado se arma en tiempo de ejecucion: el repositorio no debe
        # contener un marcador literal de clave privada (lo bloquea el guard de
        # secretos del hook de commit). El contenido es sintetico.
        cabecera = "-----BEGIN " + "PRIVATE KEY-----"
        texto = ("DUMMY_SECRET=valor-ficticio-no-real\n"
                 'CLAVE_PRIVADA="' + cabecera + "\n"
                 "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ==\n"
                 '"-----END PRIVATE KEY-----"\n'
                 "PUBLIC_URL=https://example.invalid\n")
        nombres = contrato.nombres_env(texto)
        self.assertEqual(nombres, ["CLAVE_PRIVADA", "DUMMY_SECRET", "PUBLIC_URL"])
        self.assertNotIn("MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ", " ".join(nombres))
        self.assertNotIn("PRIVATE KEY", " ".join(nombres))

    def test_ignora_fragmento_base64_suelto(self):
        texto = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ==\n"
        self.assertEqual(contrato.nombres_env(texto), [])

    def test_conserva_nombre_largo_convencional(self):
        nombre = "NOMBRE_DE_VARIABLE_MUY_LARGO_Y_CONVENCIONAL"
        self.assertEqual(contrato.nombres_env(nombre + "=1\n"), [nombre])

    def test_ignora_comentarios_y_lineas_sin_asignacion(self):
        texto = "# comentario\n\nSMTP_HOST=smtp.example.invalid\nclave suelta\n"
        self.assertEqual(contrato.nombres_env(texto), ["SMTP_HOST"])


class ArtefactosObligatorios(unittest.TestCase):
    """El manifiesto tiene que declarar los artefactos obligatorios."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        (self.base / "env.vars").write_text("DUMMY_SECRET\n", encoding="utf-8")
        (self.base / "dump.sql.age").write_bytes(b"cifrado sintetico\n")

    def tearDown(self):
        self._tmp.cleanup()

    def manifiesto(self, nombres, excluidos=()):
        digests = {}
        for nombre in nombres:
            digests[nombre] = contrato.sha256_archivo(self.base / nombre)
        datos = {"software": "kit", "version": "1.0", "database": "db",
                 "sha256": digests, "status": "completed"}
        if excluidos:
            datos["excluidos"] = list(excluidos)
        (self.base / "manifest.json").write_text(json.dumps(datos), encoding="utf-8")
        return datos

    def test_exige_declarar_los_artefactos_obligatorios(self):
        manifiesto = self.manifiesto(["env.vars"])
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.verificar_checksums(self.base, manifiesto, ("env.vars", "dump.sql.age"))
        self.assertEqual(ctx.exception.codigo, 2)
        self.assertIn("obligatorios", str(ctx.exception))

    def test_acepta_el_conjunto_declarado(self):
        manifiesto = self.manifiesto(["env.vars", "dump.sql.age"])
        self.assertEqual(contrato.verificar_checksums(self.base, manifiesto,
                                                      ("env.vars", "dump.sql.age")), manifiesto)

    def test_sin_artefactos_obligatorios_no_se_comprueba(self):
        manifiesto = self.manifiesto(["env.vars"])
        with self.assertRaises(contrato.RespaldoError):
            contrato.verificar_checksums(self.base, manifiesto, ())

    def test_ejecutar_check_exige_declarar_la_exclusion(self):
        (self.base / "dump.sql.age").unlink()
        manifiesto = self.manifiesto(["env.vars"])
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.ejecutar_check(self.base, "kit", "1.0", "db",
                                    esperados=("env.vars", "dump.sql.age"),
                                    excluibles={"dump": "dump.sql.age"})
        self.assertEqual(ctx.exception.codigo, 2)
        self.assertIn("exclusion", str(ctx.exception))
        self.assertIn("obligatorios", str(ctx.exception))

    def test_ejecutar_check_acepta_exclusion_declarada(self):
        (self.base / "dump.sql.age").unlink()
        manifiesto = self.manifiesto(["env.vars"], excluidos=["dump"])
        contrato.ejecutar_check(self.base, "kit", "1.0", "db",
                                esperados=("env.vars", "dump.sql.age"),
                                excluibles={"dump": "dump.sql.age"})

    def test_ejecutar_check_rechaza_artefacto_vacio(self):
        (self.base / "dump.sql.age").write_bytes(b"")
        manifiesto = self.manifiesto(["env.vars", "dump.sql.age"])
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.ejecutar_check(self.base, "kit", "1.0", "db",
                                    esperados=("env.vars", "dump.sql.age"),
                                    excluibles={"dump": "dump.sql.age"})
        self.assertEqual(ctx.exception.codigo, 2)


class TarHostil(unittest.TestCase):
    """El tar se valida entero antes de escribir nada."""

    def _tar(self, miembros):
        archivo = Path(self._tmp.name) / "hostil.tar.gz"
        with tarfile.open(archivo, "w:gz") as tf:
            for nombre, tipo, contenido in miembros:
                info = tarfile.TarInfo(nombre)
                if tipo == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = "../escape"
                    info.size = 0
                    tf.addfile(info)
                else:
                    info.size = len(contenido)
                    tf.addfile(info, io.BytesIO(contenido))
        return archivo

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_rechaza_entradas_duplicadas(self):
        archivo = self._tar([("datos.txt", "file", b"a"), ("datos.txt", "file", b"b")])
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.validar_tar(archivo)
        self.assertEqual(ctx.exception.codigo, 5)

    def test_rechaza_ruta_absoluta(self):
        archivo = self._tar([("/etc/passwd", "file", b"x")])
        with self.assertRaises(contrato.RespaldoError):
            contrato.validar_tar(archivo)

    def test_rechaza_traversal(self):
        archivo = self._tar([("../fuera.txt", "file", b"x")])
        with self.assertRaises(contrato.RespaldoError):
            contrato.validar_tar(archivo)

    def test_rechaza_enlace_simbolico(self):
        archivo = self._tar([("datos.txt", "symlink", b"")])
        with self.assertRaises(contrato.RespaldoError):
            contrato.validar_tar(archivo)

    def test_rechaza_archivo_ilegible(self):
        archivo = Path(self._tmp.name) / "basura.tar.gz"
        archivo.write_bytes(b"no es un tar gzip")
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.validar_tar(archivo)
        self.assertEqual(ctx.exception.codigo, 5)

    def test_acepta_tar_limpio(self):
        archivo = self._tar([("datos/demo.txt", "file", b"sintetico\n")])
        contrato.validar_tar(archivo)


class ResiduosCierre(unittest.TestCase):
    """Cierre de los residuos de la revision independiente.

    N4: la auditoria nunca sigue un enlace simbolico (ni en logs/ ni en el log).
    N5: el cifrado nunca aterriza en el destino de un enlace simbolico.
    N3: un restore-report.json que el manifiesto no declara no pasa la
    verificacion de un respaldo, pero el camino de restauracion (que lo
    escribe despues del manifiesto) sigue funcionando.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _respaldo_minimo(self):
        """Un respaldo minimo y coherente: env.vars, dump cifrado y manifiesto."""
        (self.base / "env.vars").write_text("DUMMY_SECRET\n", encoding="utf-8")
        (self.base / "dump.sql.age").write_bytes(b"cifrado sintetico\n")
        digests = {nombre: contrato.sha256_archivo(self.base / nombre)
                   for nombre in ("env.vars", "dump.sql.age")}
        manifiesto = {"software": "kit", "version": "1.0", "database": "db",
                      "sha256": digests, "status": "completed"}
        (self.base / "manifest.json").write_text(json.dumps(manifiesto), encoding="utf-8")
        return manifiesto

    # --- N4: la auditoria no sigue enlaces simbolicos ---

    def test_auditoria_rechaza_enlace_en_el_log(self):
        victima = self.base / "victima.txt"
        victima.write_text("contenido original\n", encoding="utf-8")
        (self.base / "logs").mkdir()
        (self.base / "logs" / "restore.log").symlink_to(victima)
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.auditar(self.base, operacion="restore", resultado="restaurado")
        self.assertEqual(ctx.exception.codigo, 2)
        self.assertEqual(victima.read_text(encoding="utf-8"), "contenido original\n")

    def test_auditoria_rechaza_enlace_en_el_directorio_de_logs(self):
        real = self.base / "real"
        real.mkdir()
        victima = real / "restore.log"
        victima.write_text("contenido original\n", encoding="utf-8")
        (self.base / "logs").symlink_to(real, target_is_directory=True)
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.auditar(self.base, operacion="restore", resultado="restaurado")
        self.assertEqual(ctx.exception.codigo, 2)
        self.assertEqual(victima.read_text(encoding="utf-8"), "contenido original\n")

    def test_auditoria_anade_al_log_sin_romper_el_formato(self):
        contrato.auditar(self.base, operacion="restore", kit="kit", resultado="restaurado")
        contrato.auditar(self.base, operacion="restore", kit="kit", resultado="failed")
        log = self.base / "logs" / "restore.log"
        self.assertFalse(log.is_symlink())
        lineas = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lineas), 2)
        primero = json.loads(lineas[0])
        self.assertEqual(primero["resultado"], "restaurado")
        self.assertEqual(primero["kit"], "kit")
        self.assertIn("ts", primero)
        self.assertEqual(json.loads(lineas[1])["resultado"], "failed")
        self.assertEqual(oct(log.stat().st_mode & 0o777), oct(0o600))

    # --- N5: el cifrado no aterriza en el destino de un enlace ---

    def test_cifrar_con_age_rechaza_enlace_en_el_destino(self):
        victima = self.base / "victima.txt"
        victima.write_text("contenido original\n", encoding="utf-8")
        destino = self.base / "dump.sql.age"
        destino.symlink_to(victima)
        with mock.patch.object(contrato.shutil, "which", return_value="/usr/bin/age"):
            with self.assertRaises(contrato.RespaldoError) as ctx:
                contrato.cifrar_con_age(lambda flujo: None, destino, RECEPTOR_FICTICIO)
        self.assertEqual(ctx.exception.codigo, 2)
        self.assertEqual(victima.read_text(encoding="utf-8"), "contenido original\n")

    # --- N3: el informe de restauracion no declarado no se cuela ---

    def test_verificacion_rechaza_un_informe_no_declarado(self):
        self._respaldo_minimo()
        (self.base / "restore-report.json").write_text(
            json.dumps({"resultado": "restaurado"}), encoding="utf-8")
        with self.assertRaises(contrato.RespaldoError) as ctx:
            contrato.ejecutar_check(self.base, "kit", "1.0", "db",
                                    esperados=("env.vars", "dump.sql.age"))
        self.assertEqual(ctx.exception.codigo, 2)
        self.assertIn("restore-report.json", str(ctx.exception))

    def test_el_informe_se_puede_escribir_tras_la_restauracion(self):
        self._respaldo_minimo()
        contrato.escribir_informe(self.base, software="kit", resultado="restaurado")
        self.assertTrue((self.base / "restore-report.json").is_file())
        # El camino de restauracion tolera su propio informe: lo escribe
        # despues del manifiesto y todavia no puede declararlo.
        contrato.ejecutar_check(self.base, "kit", "1.0", "db",
                                esperados=("env.vars", "dump.sql.age"),
                                permitir_informe_no_declarado=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
