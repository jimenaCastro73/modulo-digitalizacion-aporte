# -*- coding: utf-8 -*-
"""
test_registro_regresion.py — PRUEBAS DE CAJA NEGRA / REGRESIÓN
===============================================================
Modelo: digitalizacion.registro  (T-06)

Cobertura (flujos funcionales end-to-end):
  CN-01  Crear registro válido en cada etapa
  CN-02  Editar registro → actualiza produccion_principal
  CN-03  Duplicar registro (action_duplicar_para_hoy)
  CN-04  No permitir eliminar miembro con registros (integridad referencial)
  CN-05  Flujo de creación masiva (create_multi)
  CN-06  KPIs del líder (get_kpis_lider)
  CN-07  Resumen por etapa (get_resumen_por_etapa)
  CN-08  Participación del equipo (get_participacion_equipo)
  CN-09  Regresión RG-01: valores negativos bloqueados post-write
  CN-10  Regresión RG-02: fecha futura bloqueada post-write

Ejecutar:
  odoo --test-enable -d digitalizacion_dev \
       --test-tags '/digitalizacion:test_registro_regresion'
"""

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("digitalizacion", "regresion", "registro")
class TestRegistroRegresion(TransactionCase):
    """Pruebas de caja negra / regresión sobre digitalizacion.registro."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Etapa = cls.env["digitalizacion.etapa"]
        cls.etapa_limpieza = Etapa.search([("name", "=", "Limpieza")], limit=1)
        cls.etapa_ordenado = Etapa.search([("name", "=", "Ordenado")], limit=1)
        cls.etapa_digitalizado = Etapa.search([("name", "=", "Digitalizado")], limit=1)
        cls.etapa_editado = Etapa.search([("name", "=", "Editado")], limit=1)
        cls.etapa_indexado = Etapa.search([("name", "=", "Indexado")], limit=1)

        cls.proyecto = cls.env["digitalizacion.proyecto"].create(
            {
                "name": "Proyecto Test Regresión",
                "fecha_inicio": date.today(),
                "state": "en_curso",
            }
        )

        cls.partner_a = cls.env["res.partner"].create({"name": "Digitalizador A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Digitalizador B"})

        cls.miembro_a = cls.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": cls.proyecto.id,
                "partner_id": cls.partner_a.id,
                "fecha_integracion": date.today(),
            }
        )
        cls.miembro_b = cls.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": cls.proyecto.id,
                "partner_id": cls.partner_b.id,
                "fecha_integracion": date.today(),
            }
        )

    def _crear_registro(self, **kwargs):
        """Helper: crea un registro con valores base para Limpieza."""
        vals = {
            "proyecto_id": self.proyecto.id,
            "miembro_id": self.miembro_a.id,
            "etapa_id": self.etapa_limpieza.id,
            "fecha": date.today(),
            "no_expedientes": 10,
            "total_folios": 100,
        }
        vals.update(kwargs)
        return self.env["digitalizacion.registro"].create(vals)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-01 — Crear registro válido en cada etapa
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn01_crear_registro_limpieza(self):
        """CN-01a: Crea registro válido para etapa Limpieza."""
        r = self._crear_registro(no_expedientes=5, total_folios=50)
        self.assertTrue(r.id)
        self.assertEqual(r.etapa_nombre, "Limpieza")

    def test_cn01_crear_registro_ordenado(self):
        """CN-01b: Crea registro válido para etapa Ordenado."""
        r = self._crear_registro(
            etapa_id=self.etapa_ordenado.id,
            no_expedientes=8,
            total_folios=80,
        )
        self.assertTrue(r.id)

    def test_cn01_crear_registro_digitalizado(self):
        """CN-01c: Crea registro válido para etapa Digitalizado."""
        r = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_digitalizado.id,
                "fecha": date.today(),
                "total_escaneos": 300,
                "total_folios": 250,
            }
        )
        self.assertTrue(r.id)
        self.assertEqual(r.produccion_principal, 300)

    def test_cn01_crear_registro_editado(self):
        """CN-01d: Crea registro válido para etapa Editado."""
        r = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_editado.id,
                "fecha": date.today(),
                "expedientes_editados": 15,
                "folios_editados": 120,
            }
        )
        self.assertTrue(r.id)
        self.assertEqual(r.unidad_produccion, "exp. editados")

    def test_cn01_crear_registro_indexado(self):
        """CN-01e: Crea registro válido para etapa Indexado."""
        r = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_indexado.id,
                "fecha": date.today(),
                "expedientes_indexados": 12,
                "folios_indexados": 110,
            }
        )
        self.assertTrue(r.id)
        self.assertEqual(r.unidad_produccion, "exp. indexados")

    # ──────────────────────────────────────────────────────────────────────────
    # CN-02 — Editar registro → actualiza produccion_principal
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn02_editar_actualiza_produccion(self):
        """CN-02: Editar no_expedientes recalcula produccion_principal."""
        r = self._crear_registro(no_expedientes=10, total_folios=50)
        self.assertEqual(r.produccion_principal, 10)
        r.write({"no_expedientes": 25})
        self.assertEqual(r.produccion_principal, 25)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-03 — Duplicar registro (action_duplicar_para_hoy)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn03_duplicar_para_hoy(self):
        """CN-03: La acción duplica el registro con fecha = hoy."""
        fecha_pasada = date.today() - timedelta(days=5)
        original = self._crear_registro(fecha=fecha_pasada, no_expedientes=7)
        result = original.action_duplicar_para_hoy()
        duplicado = self.env["digitalizacion.registro"].browse(result["res_id"])
        self.assertEqual(duplicado.fecha, date.today())
        self.assertEqual(duplicado.no_expedientes, 7)
        self.assertNotEqual(duplicado.id, original.id)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-04 — Integridad referencial (ondelete=restrict en miembro_id)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn04_no_eliminar_miembro_con_registros(self):
        """CN-04: No se puede eliminar un miembro que tiene registros asociados."""
        self._crear_registro(miembro_id=self.miembro_b.id)
        # ondelete='restrict' → unlink lanza IntegrityError (nivel DB)
        from odoo.exceptions import UserError
        excepcion_ok = False
        try:
            with self.env.cr.savepoint():
                self.miembro_b.unlink()
        except (UserError, Exception):
            excepcion_ok = True
        self.assertTrue(excepcion_ok, "Debería haberse lanzado error de restricción FK")

    # ──────────────────────────────────────────────────────────────────────────
    # CN-05 — Creación masiva (create_multi)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn05_create_multi(self):
        """CN-05: Crear varios registros en una sola llamada create()."""
        vals_list = [
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_limpieza.id,
                "fecha": date.today() - timedelta(days=i),
                "no_expedientes": 10 + i,
                "total_folios": 100,
            }
            for i in range(3)
        ]
        registros = self.env["digitalizacion.registro"].create(vals_list)
        self.assertEqual(len(registros), 3)
        # Todos deben tener lider_id del usuario en sesión
        for r in registros:
            self.assertEqual(r.lider_id, self.env.user)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-06 — KPIs del líder (get_kpis_lider)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn06_get_kpis_lider(self):
        """CN-06: get_kpis_lider agrega correctamente los totales."""
        # Crear registros conocidos
        self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_digitalizado.id,
                "fecha": date.today(),
                "total_escaneos": 200,
                "total_folios": 150,
            }
        )
        self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_digitalizado.id,
                "fecha": date.today() - timedelta(days=1),
                "total_escaneos": 100,
                "total_folios": 80,
            }
        )

        kpis = self.env["digitalizacion.registro"].get_kpis_lider(
            self.env.user.id,
            domain_extra=[("proyecto_id", "=", self.proyecto.id)],
        )

        self.assertIn("escaneos", kpis)
        self.assertIn("folios_fisicos", kpis)
        self.assertIn("total_registros", kpis)
        self.assertGreaterEqual(kpis["escaneos"], 300)
        self.assertGreaterEqual(kpis["total_registros"], 2)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-07 — Resumen por etapa (get_resumen_por_etapa)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn07_resumen_por_etapa(self):
        """CN-07: get_resumen_por_etapa retorna lista con etapas correctas."""
        self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_digitalizado.id,
                "fecha": date.today(),
                "total_escaneos": 400,
                "total_folios": 300,
            }
        )
        resumen = self.env["digitalizacion.registro"].get_resumen_por_etapa(
            self.proyecto.id
        )
        self.assertIsInstance(resumen, list)
        etapas_en_resumen = [r["etapa"] for r in resumen]
        self.assertIn("Digitalizado", etapas_en_resumen)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-08 — Participación del equipo (get_participacion_equipo)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn08_participacion_equipo(self):
        """CN-08: get_participacion_equipo retorna estructura con segmentos."""
        # Crear registros para dos miembros
        for miembro in (self.miembro_a, self.miembro_b):
            self.env["digitalizacion.registro"].create(
                {
                    "proyecto_id": self.proyecto.id,
                    "miembro_id": miembro.id,
                    "etapa_id": self.etapa_limpieza.id,
                    "fecha": date.today(),
                    "no_expedientes": 5,
                    "total_folios": 50,
                }
            )

        resultado = self.env["digitalizacion.registro"].get_participacion_equipo(
            self.proyecto.id
        )
        self.assertIn("etapas", resultado)
        self.assertIn("miembros", resultado)
        self.assertGreaterEqual(len(resultado["miembros"]), 2)
        # Cada miembro debe tener segmentos
        for m in resultado["miembros"]:
            self.assertIn("segmentos", m)
            self.assertIn("total", m)

    # ──────────────────────────────────────────────────────────────────────────
    # CN-09 — Regresión: valores negativos bloqueados también en write()
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn09_regresion_write_negativo(self):
        """RG-01: Valores negativos también están bloqueados en write()."""
        r = self._crear_registro(no_expedientes=10, total_folios=50)
        with self.assertRaises(ValidationError):
            r.write({"no_expedientes": -5})

    def test_cn09_regresion_write_total_folios_negativo(self):
        """RG-01b: total_folios negativo bloqueado en write()."""
        r = self._crear_registro(no_expedientes=10, total_folios=50)
        with self.assertRaises(ValidationError):
            r.write({"total_folios": -1})

    # ──────────────────────────────────────────────────────────────────────────
    # CN-10 — Regresión: fecha futura bloqueada también en write()
    # ──────────────────────────────────────────────────────────────────────────

    def test_cn10_regresion_write_fecha_futura(self):
        """RG-02: Fecha futura también está bloqueada en write()."""
        r = self._crear_registro()
        with self.assertRaises(ValidationError):
            r.write({"fecha": date.today() + timedelta(days=1)})
