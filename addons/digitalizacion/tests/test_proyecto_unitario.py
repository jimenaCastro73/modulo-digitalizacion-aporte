# -*- coding: utf-8 -*-
"""
test_proyecto_unitario.py — PRUEBAS DE CAJA BLANCA / UNITARIAS
===============================================================
Modelo: digitalizacion.proyecto  (T-03)

Cobertura:
  PY-01  _check_fechas          → fecha_fin < fecha_inicio
  PY-02  _check_meta_escaneos   → meta_escaneos < 0
  PY-03  _compute_progreso      → cálculo de porcentaje
  PY-04  _sql_constraints       → nombre único
  PY-05  action_archivar        → desactiva proyecto y líderes
  PY-06  action_ver_registros   → retorna acción de ventana correcta
  PY-07  _compute_duracion_estimada → cálculo de días

Ejecutar:
  odoo --test-enable -d digitalizacion_dev \
       --test-tags '/digitalizacion:test_proyecto_unitario'
"""

from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("digitalizacion", "unitario", "proyecto")
class TestProyectoUnitario(TransactionCase):
    """Pruebas de caja blanca sobre digitalizacion.proyecto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = date.today()

    def _crear_proyecto(self, **kwargs):
        vals = {
            "name": f"Proyecto Test {self.hoy}",
            "fecha_inicio": self.hoy,
            "state": "activo",
            "meta_escaneos": 500,
        }
        vals.update(kwargs)
        return self.env["digitalizacion.proyecto"].create(vals)

    # ──────────────────────────────────────────────────────────────────────────
    # PY-01 — _check_fechas
    # ──────────────────────────────────────────────────────────────────────────

    def test_py01_fecha_fin_anterior_a_inicio(self):
        """PY-01a: fecha_fin_estimada < fecha_inicio lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self._crear_proyecto(
                name="Proyecto Fechas Inválidas",
                fecha_inicio=self.hoy,
                fecha_fin_estimada=self.hoy - timedelta(days=1),
            )

    def test_py01_fecha_fin_igual_a_inicio(self):
        """PY-01b: fecha_fin_estimada == fecha_inicio es válido."""
        p = self._crear_proyecto(
            name="Proyecto Misma Fecha",
            fecha_inicio=self.hoy,
            fecha_fin_estimada=self.hoy,
        )
        self.assertTrue(p.id)

    def test_py01_fecha_fin_posterior_valida(self):
        """PY-01c: fecha_fin_estimada > fecha_inicio es válida."""
        p = self._crear_proyecto(
            name="Proyecto Fechas OK",
            fecha_inicio=self.hoy,
            fecha_fin_estimada=self.hoy + timedelta(days=30),
        )
        self.assertEqual(p.duracion_estimada, 30)

    # ──────────────────────────────────────────────────────────────────────────
    # PY-02 — _check_meta_escaneos
    # ──────────────────────────────────────────────────────────────────────────

    def test_py02_meta_escaneos_negativa(self):
        """PY-02a: meta_escaneos < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self._crear_proyecto(name="Meta Negativa", meta_escaneos=-1)

    def test_py02_meta_escaneos_cero_permitida(self):
        """PY-02b: meta_escaneos == 0 es válido (sin meta definida)."""
        p = self._crear_proyecto(name="Proyecto Sin Meta", meta_escaneos=0)
        self.assertEqual(p.meta_escaneos, 0)

    # ──────────────────────────────────────────────────────────────────────────
    # PY-03 — _compute_progreso
    # ──────────────────────────────────────────────────────────────────────────

    def test_py03_progreso_sin_meta(self):
        """PY-03a: Si meta_escaneos == 0, progreso = 0.0."""
        p = self._crear_proyecto(name="Sin Meta Progreso", meta_escaneos=0)
        self.assertEqual(p.progreso, 0.0)

    def test_py03_progreso_con_registros(self):
        """PY-03b: Progreso se calcula tras crear registros de escaneo."""
        p = self._crear_proyecto(name="Progreso con Registros", meta_escaneos=1000)

        etapa_digitalizado = self.env["digitalizacion.etapa"].search(
            [("name", "=", "Digitalizado")], limit=1
        )
        partner = self.env["res.partner"].create({"name": "Digitalizador Progreso"})
        miembro = self.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": p.id,
                "partner_id": partner.id,
                "fecha_integracion": self.hoy,
            }
        )
        self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": p.id,
                "miembro_id": miembro.id,
                "etapa_id": etapa_digitalizado.id,
                "fecha": self.hoy,
                "total_escaneos": 500,
                "total_folios": 400,
            }
        )
        p.invalidate_recordset()
        self.assertAlmostEqual(p.progreso, 50.0, places=1)

    def test_py03_progreso_no_supera_100(self):
        """PY-03c: Progreso no supera el 100% aunque los escaneos excedan la meta."""
        p = self._crear_proyecto(name="Progreso Máximo", meta_escaneos=100)
        etapa_digitalizado = self.env["digitalizacion.etapa"].search(
            [("name", "=", "Digitalizado")], limit=1
        )
        partner = self.env["res.partner"].create({"name": "Digitalizador 100"})
        miembro = self.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": p.id,
                "partner_id": partner.id,
                "fecha_integracion": self.hoy,
            }
        )
        self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": p.id,
                "miembro_id": miembro.id,
                "etapa_id": etapa_digitalizado.id,
                "fecha": self.hoy,
                "total_escaneos": 500,
                "total_folios": 100,
            }
        )
        p.invalidate_recordset()
        self.assertLessEqual(p.progreso, 100.0)

    # ──────────────────────────────────────────────────────────────────────────
    # PY-04 — SQL constraint nombre único
    # ──────────────────────────────────────────────────────────────────────────

    def test_py04_nombre_unico(self):
        """PY-04: No se puede crear dos proyectos con el mismo nombre."""
        nombre = "Proyecto Nombre Único Test"
        self._crear_proyecto(name=nombre)
        excepcion_ok = False
        try:
            with self.env.cr.savepoint():
                self._crear_proyecto(name=nombre)
        except (UserError, Exception):
            excepcion_ok = True
        self.assertTrue(excepcion_ok, "Debería haberse lanzado error de unicidad")

    # ──────────────────────────────────────────────────────────────────────────
    # PY-05 — action_archivar
    # ──────────────────────────────────────────────────────────────────────────

    def test_py05_action_archivar(self):
        """PY-05: action_archivar desactiva el proyecto."""
        p = self._crear_proyecto(name="Proyecto a Archivar")
        self.assertTrue(p.active)
        p.action_archivar()
        self.assertFalse(p.active)

    def test_py05_action_activar(self):
        """PY-05b: action_activar reactiva un proyecto archivado."""
        p = self._crear_proyecto(name="Proyecto a Reactivar")
        p.action_archivar()
        self.assertFalse(p.active)
        p.with_context(active_test=False).action_activar()
        p.invalidate_recordset()
        self.assertTrue(p.active)

    # ──────────────────────────────────────────────────────────────────────────
    # PY-06 — action_ver_registros
    # ──────────────────────────────────────────────────────────────────────────

    def test_py06_action_ver_registros(self):
        """PY-06: action_ver_registros retorna una acción de ventana válida."""
        p = self._crear_proyecto(name="Proyecto Ver Registros")
        action = p.action_ver_registros()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "digitalizacion.registro")
        self.assertIn(("proyecto_id", "=", p.id), action["domain"])

    # ──────────────────────────────────────────────────────────────────────────
    # PY-07 — _compute_duracion_estimada
    # ──────────────────────────────────────────────────────────────────────────

    def test_py07_duracion_estimada_calculada(self):
        """PY-07: duracion_estimada = diferencia en días entre inicio y fin."""
        p = self._crear_proyecto(
            name="Proyecto Duración",
            fecha_inicio=self.hoy,
            fecha_fin_estimada=self.hoy + timedelta(days=90),
        )
        self.assertEqual(p.duracion_estimada, 90)

    def test_py07_duracion_sin_fecha_fin(self):
        """PY-07b: Sin fecha_fin_estimada, duracion_estimada = 0."""
        p = self._crear_proyecto(name="Sin Fecha Fin")
        self.assertEqual(p.duracion_estimada, 0)
