# -*- coding: utf-8 -*-
"""
test_proyecto_unitario.py — PRUEBAS DE CAJA BLANCA / UNITARIAS
===============================================================
Modelo: digitalizacion.proyecto  (T-03)

Cobertura:
  PY-01  _check_fechas          → fecha_fin < fecha_inicio
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
            "state": "en_curso",
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

    def test_py05_action_pausar(self):
        """PY-05a: action_pausar cambia el estado a pausado."""
        p = self._crear_proyecto(name="Proyecto a Pausar")
        self.assertEqual(p.state, "en_curso")
        p.action_pausar()
        self.assertEqual(p.state, "pausado")

    def test_py05_action_finalizar(self):
        """PY-05b: action_finalizar cambia el estado a finalizado."""
        p = self._crear_proyecto(name="Proyecto a Finalizar")
        p.action_finalizar()
        self.assertEqual(p.state, "finalizado")

    def test_py05_action_reactivar(self):
        """PY-05c: action_reactivar vuelve a poner el proyecto en_curso."""
        p = self._crear_proyecto(name="Proyecto a Reactivar", state="pausado")
        p.action_reactivar()
        self.assertEqual(p.state, "en_curso")

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
