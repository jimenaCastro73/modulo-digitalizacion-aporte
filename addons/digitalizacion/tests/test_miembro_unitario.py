# -*- coding: utf-8 -*-
"""
test_miembro_unitario.py — PRUEBAS DE CAJA BLANCA / UNITARIAS
=============================================================
Modelo: digitalizacion.miembro_proyecto  (T-05)

Cobertura:
  MP-01  _check_fechas            → fecha_salida < fecha_integracion
  MP-02  _check_lider_unico       → un solo líder activo por proyecto
  MP-03  _sql_constraints         → UNIQUE(proyecto_id, partner_id)
  MP-04  action_registrar_salida  → asigna fecha_salida y desactiva
  MP-05  action_reintegrar        → limpia fecha_salida y reactiva
  MP-06  crear_desde_portal       → crea o reutiliza partner/miembro
  MP-07  _compute_display_name    → formato "Nombre (Proyecto)"
  MP-08  Regresión: doble salida  → error si ya tiene fecha_salida

Ejecutar:
  odoo --test-enable -d digitalizacion_dev \
       --test-tags '/digitalizacion:test_miembro_unitario'
"""

from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("digitalizacion", "unitario", "miembro")
class TestMiembroUnitario(TransactionCase):
    """Pruebas de caja blanca sobre digitalizacion.miembro_proyecto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = date.today()
        cls.proyecto = cls.env["digitalizacion.proyecto"].create(
            {
                "name": "Proyecto Miembro Test",
                "fecha_inicio": cls.hoy,
                "state": "activo",
            }
        )

    def _crear_partner(self, nombre="Test Partner"):
        return self.env["res.partner"].create({"name": nombre})

    def _crear_miembro(self, partner=None, **kwargs):
        if partner is None:
            partner = self._crear_partner()
        vals = {
            "proyecto_id": self.proyecto.id,
            "partner_id": partner.id,
            "fecha_integracion": self.hoy,
        }
        vals.update(kwargs)
        return self.env["digitalizacion.miembro_proyecto"].create(vals)

    # ──────────────────────────────────────────────────────────────────────────
    # MP-01 — _check_fechas
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp01_fecha_salida_anterior_a_integracion(self):
        """MP-01a: fecha_salida < fecha_integracion lanza ValidationError."""
        miembro = self._crear_miembro()
        with self.assertRaises(ValidationError):
            miembro.write(
                {
                    "fecha_salida": self.hoy - timedelta(days=1),
                }
            )

    def test_mp01_fecha_salida_igual_integracion_permitida(self):
        """MP-01b: fecha_salida == fecha_integracion es válida."""
        miembro = self._crear_miembro()
        # No debe lanzar error — fecha_salida el mismo día que integracion
        miembro.write({"fecha_salida": self.hoy})
        self.assertEqual(miembro.fecha_salida, self.hoy)

    # ──────────────────────────────────────────────────────────────────────────
    # MP-02 — _check_lider_unico
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp02_lider_unico_por_proyecto(self):
        """MP-02: Solo puede haber un líder activo por proyecto."""
        partner1 = self._crear_partner("Líder 1")
        partner2 = self._crear_partner("Líder 2")
        miembro1 = self._crear_miembro(partner=partner1)
        miembro2 = self._crear_miembro(partner=partner2)

        # Necesita usuario portal para activar liderazgo
        # Solo probamos la constraint de lider_unico (sin portal usuario)
        # Marcamos directamente via SQL para evitar _activar_liderazgo que requiere portal
        self.env.cr.execute(
            "UPDATE digitalizacion_miembro_proyecto SET es_lider=true WHERE id=%s",
            (miembro1.id,),
        )
        miembro1.invalidate_recordset()

        # Intentar poner miembro2 como líder debe fallar por la constraint
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.miembro_proyecto"].browse(miembro2.id).write(
                {"es_lider": True}
            )

    # ──────────────────────────────────────────────────────────────────────────
    # MP-03 — SQL constraint UNIQUE
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp03_unicidad_partner_proyecto(self):
        """MP-03: No se puede agregar el mismo partner dos veces al proyecto."""
        partner = self._crear_partner("Partner Único")
        self._crear_miembro(partner=partner)
        excepcion_ok = False
        try:
            with self.env.cr.savepoint():
                self._crear_miembro(partner=partner)
        except (UserError, Exception):
            excepcion_ok = True
        self.assertTrue(excepcion_ok, "Debería haberse lanzado error de unicidad")

    # ──────────────────────────────────────────────────────────────────────────
    # MP-04 — action_registrar_salida
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp04_registrar_salida_asigna_fecha(self):
        """MP-04a: action_registrar_salida asigna fecha_salida = hoy."""
        miembro = self._crear_miembro()
        self.assertFalse(miembro.fecha_salida)
        miembro.action_registrar_salida()
        miembro.invalidate_recordset()
        self.assertEqual(miembro.fecha_salida, self.hoy)

    def test_mp04_registrar_salida_desactiva(self):
        """MP-04b: action_registrar_salida desactiva al miembro."""
        miembro = self._crear_miembro()
        miembro.action_registrar_salida()
        miembro.invalidate_recordset()
        self.assertFalse(miembro.active)

    # ──────────────────────────────────────────────────────────────────────────
    # MP-05 — action_reintegrar
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp05_reintegrar_limpia_fecha_salida(self):
        """MP-05a: action_reintegrar limpia fecha_salida."""
        miembro = self._crear_miembro()
        miembro.action_registrar_salida()
        miembro.with_context(active_test=False).action_reintegrar()
        miembro.invalidate_recordset()
        self.assertFalse(miembro.fecha_salida)

    def test_mp05_reintegrar_reactiva(self):
        """MP-05b: action_reintegrar vuelve a activar al miembro."""
        miembro = self._crear_miembro()
        miembro.action_registrar_salida()
        miembro.with_context(active_test=False).action_reintegrar()
        miembro.invalidate_recordset()
        self.assertTrue(miembro.active)

    # ──────────────────────────────────────────────────────────────────────────
    # MP-06 — crear_desde_portal
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp06_crear_con_nombre_nuevo(self):
        """MP-06a: crear_desde_portal crea un partner si no existe."""
        resultado = self.env["digitalizacion.miembro_proyecto"].crear_desde_portal(
            proyecto_id=self.proyecto.id,
            nombre="Nuevo Miembro Portal",
        )
        self.assertIn("id", resultado)
        self.assertIn("name", resultado)
        self.assertEqual(resultado["name"], "Nuevo Miembro Portal")

    def test_mp06_reutiliza_partner_existente(self):
        """MP-06b: crear_desde_portal reutiliza el partner si ya existe."""
        nombre = "Partner Reutilizable Test"
        # Primera creación
        resultado1 = self.env["digitalizacion.miembro_proyecto"].crear_desde_portal(
            proyecto_id=self.proyecto.id,
            nombre=nombre,
        )
        # Intentar crear de nuevo en otro proyecto (debe crear un nuevo miembro)
        otro_proyecto = self.env["digitalizacion.proyecto"].create(
            {
                "name": "Otro Proyecto Portal",
                "fecha_inicio": self.hoy,
                "state": "activo",
            }
        )
        resultado2 = self.env["digitalizacion.miembro_proyecto"].crear_desde_portal(
            proyecto_id=otro_proyecto.id,
            nombre=nombre,
        )
        # El nombre debe ser el mismo (mismo partner)
        self.assertEqual(resultado1["name"], resultado2["name"])

    def test_mp06_nombre_vacio_lanza_error(self):
        """MP-06c: crear_desde_portal con nombre vacío lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.miembro_proyecto"].crear_desde_portal(
                proyecto_id=self.proyecto.id,
                nombre="",
            )

    # ──────────────────────────────────────────────────────────────────────────
    # MP-07 — _compute_display_name
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp07_display_name_formato(self):
        """MP-07: display_name tiene formato 'Nombre (Proyecto)'."""
        partner = self._crear_partner("Display Test")
        miembro = self._crear_miembro(partner=partner)
        self.assertIn("Display Test", miembro.display_name)
        self.assertIn(self.proyecto.name, miembro.display_name)
        self.assertIn("(", miembro.display_name)
        self.assertIn(")", miembro.display_name)

    # ──────────────────────────────────────────────────────────────────────────
    # MP-08 — Regresión: doble llamada a action_registrar_salida
    # ──────────────────────────────────────────────────────────────────────────

    def test_mp08_regresion_doble_salida(self):
        """RG-03: Segunda llamada a action_registrar_salida lanza ValidationError."""
        miembro = self._crear_miembro()
        miembro.action_registrar_salida()
        with self.assertRaises(ValidationError):
            miembro.with_context(active_test=False).action_registrar_salida()
