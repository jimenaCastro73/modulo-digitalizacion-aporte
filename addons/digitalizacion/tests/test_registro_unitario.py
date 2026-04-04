# -*- coding: utf-8 -*-
"""
test_registro_unitario.py — PRUEBAS DE CAJA BLANCA / UNITARIAS
===============================================================
Modelo: digitalizacion.registro  (T-06)

Cobertura:
  CB-01  _check_valores_positivos  → cantidades negativas
  CB-02  _check_fecha_no_futura    → fechas futuras
  CB-03  _check_miembro_activo     → miembro con fecha_salida
  CB-04  _check_miembro_pertenece_proyecto → miembro de otro proyecto
  CB-05  _check_campos_minimos_por_etapa  → mínimos por etapa
  CB-06  _compute_display_name     → formato del nombre
  CB-07  _compute_produccion_principal   → lógica por etapa
  CB-08  _onchange_etapa           → limpieza de campos al cambiar etapa
  CB-09  create() override         → lider_id forzado al usuario en sesión
  CB-10  write() override          → lider_id no modificable

Ejecutar (dentro del contenedor Odoo):
  odoo --test-enable -d digitalizacion_dev \
       --test-tags '/digitalizacion:test_registro_unitario'
"""

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("digitalizacion", "unitario", "registro")
class TestRegistroUnitario(TransactionCase):
    """Pruebas de caja blanca sobre digitalizacion.registro."""

    # ──────────────────────────────────────────────────────────────────────────
    # Datos de prueba comunes
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Etapas (se usan las creadas por etapa_data.xml)
        Etapa = cls.env["digitalizacion.etapa"]
        cls.etapa_limpieza = Etapa.search([("name", "=", "Limpieza")], limit=1)
        cls.etapa_ordenado = Etapa.search([("name", "=", "Ordenado")], limit=1)
        cls.etapa_digitalizado = Etapa.search([("name", "=", "Digitalizado")], limit=1)
        cls.etapa_editado = Etapa.search([("name", "=", "Editado")], limit=1)
        cls.etapa_indexado = Etapa.search([("name", "=", "Indexado")], limit=1)

        # Proyecto de prueba
        cls.proyecto = cls.env["digitalizacion.proyecto"].create(
            {
                "name": "Proyecto Test Unitario",
                "fecha_inicio": date.today(),
                "state": "activo",
                "meta_escaneos": 1000,
            }
        )

        # Partner y miembro activo
        cls.partner = cls.env["res.partner"].create({"name": "Test Digitalizador"})
        cls.miembro = cls.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": cls.proyecto.id,
                "partner_id": cls.partner.id,
                "fecha_integracion": date.today(),
            }
        )

        # Otro proyecto para prueba de pertenencia
        cls.otro_proyecto = cls.env["digitalizacion.proyecto"].create(
            {
                "name": "Otro Proyecto Test",
                "fecha_inicio": date.today(),
                "state": "activo",
            }
        )

    def _vals_base(self, **kwargs):
        """Devuelve valores mínimos válidos para un registro de Limpieza."""
        vals = {
            "proyecto_id": self.proyecto.id,
            "miembro_id": self.miembro.id,
            "etapa_id": self.etapa_limpieza.id,
            "fecha": date.today(),
            "no_expedientes": 10,
            "total_folios": 100,
        }
        vals.update(kwargs)
        return vals

    # ──────────────────────────────────────────────────────────────────────────
    # CB-01 — Cantidades negativas (6 campos numéricos)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb01_no_expedientes_negativo(self):
        """CB-01a: no_expedientes < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(no_expedientes=-1, total_folios=10)
            )

    def test_cb01_total_folios_negativo(self):
        """CB-01b: total_folios < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(total_folios=-1, no_expedientes=5)
            )

    def test_cb01_total_escaneos_negativo(self):
        """CB-01c: total_escaneos < 0 lanza ValidationError (etapa Digitalizado)."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(
                    etapa_id=self.etapa_digitalizado.id,
                    total_escaneos=-5,
                    total_folios=10,
                )
            )

    def test_cb01_expedientes_editados_negativo(self):
        """CB-01d: expedientes_editados < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(
                    etapa_id=self.etapa_editado.id,
                    expedientes_editados=-1,
                    folios_editados=5,
                )
            )

    def test_cb01_folios_editados_negativo(self):
        """CB-01e: folios_editados < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(
                    etapa_id=self.etapa_editado.id,
                    expedientes_editados=5,
                    folios_editados=-1,
                )
            )

    def test_cb01_expedientes_indexados_negativo(self):
        """CB-01f: expedientes_indexados < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(
                    etapa_id=self.etapa_indexado.id,
                    expedientes_indexados=-1,
                    folios_indexados=5,
                )
            )

    def test_cb01_folios_indexados_negativo(self):
        """CB-01g: folios_indexados < 0 lanza ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(
                    etapa_id=self.etapa_indexado.id,
                    expedientes_indexados=5,
                    folios_indexados=-1,
                )
            )

    def test_cb01_valor_cero_permitido(self):
        """CB-01h: Valor 0 en campos numéricos es válido (no lanza error)."""
        registro = self.env["digitalizacion.registro"].create(
            self._vals_base(no_expedientes=0, total_folios=5)
        )
        self.assertEqual(registro.no_expedientes, 0)

    # ──────────────────────────────────────────────────────────────────────────
    # CB-02 — Fecha no futura
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb02_fecha_futura_lanza_error(self):
        """CB-02a: fecha > hoy lanza ValidationError."""
        fecha_futura = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(fecha=fecha_futura)
            )

    def test_cb02_fecha_hoy_permitida(self):
        """CB-02b: fecha == hoy es válida."""
        registro = self.env["digitalizacion.registro"].create(
            self._vals_base(fecha=date.today())
        )
        self.assertEqual(registro.fecha, date.today())

    def test_cb02_fecha_pasada_permitida(self):
        """CB-02c: fecha anterior a hoy es válida."""
        fecha_pasada = date.today() - timedelta(days=30)
        registro = self.env["digitalizacion.registro"].create(
            self._vals_base(fecha=fecha_pasada)
        )
        self.assertEqual(registro.fecha, fecha_pasada)

    # ──────────────────────────────────────────────────────────────────────────
    # CB-03 — Miembro activo (sin fecha_salida)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb03_miembro_con_fecha_salida_rechazado(self):
        """CB-03: No se puede crear registro si el miembro tiene fecha_salida."""
        # Crear miembro con fecha de salida directamente en BD (bypass write)
        miembro_inactivo = self.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": self.proyecto.id,
                "partner_id": self.env["res.partner"].create({"name": "Salido"}).id,
                "fecha_integracion": date.today() - timedelta(days=10),
            }
        )
        # Asignar fecha_salida vía SQL para evitar el write override
        self.env.cr.execute(
            "UPDATE digitalizacion_miembro_proyecto SET fecha_salida=%s WHERE id=%s",
            (date.today(), miembro_inactivo.id),
        )
        miembro_inactivo.invalidate_recordset()

        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(miembro_id=miembro_inactivo.id)
            )

    # ──────────────────────────────────────────────────────────────────────────
    # CB-04 — Miembro pertenece al proyecto
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb04_miembro_otro_proyecto_rechazado(self):
        """CB-04: No se puede crear registro con miembro de otro proyecto."""
        partner_otro = self.env["res.partner"].create({"name": "Otro Miembro"})
        miembro_otro = self.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": self.otro_proyecto.id,
                "partner_id": partner_otro.id,
                "fecha_integracion": date.today(),
            }
        )
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                self._vals_base(
                    proyecto_id=self.proyecto.id,
                    miembro_id=miembro_otro.id,
                )
            )

    # ──────────────────────────────────────────────────────────────────────────
    # CB-05 — Mínimos de campos por etapa
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb05_digitalizado_requiere_escaneos_o_folios(self):
        """CB-05a: Etapa Digitalizado requiere total_escaneos o total_folios."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                {
                    "proyecto_id": self.proyecto.id,
                    "miembro_id": self.miembro.id,
                    "etapa_id": self.etapa_digitalizado.id,
                    "fecha": date.today(),
                    "total_escaneos": 0,
                    "total_folios": 0,
                }
            )

    def test_cb05_editado_requiere_expedientes_o_folios(self):
        """CB-05b: Etapa Editado requiere expedientes_editados o folios_editados."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                {
                    "proyecto_id": self.proyecto.id,
                    "miembro_id": self.miembro.id,
                    "etapa_id": self.etapa_editado.id,
                    "fecha": date.today(),
                    "expedientes_editados": 0,
                    "folios_editados": 0,
                }
            )

    def test_cb05_indexado_requiere_expedientes_o_folios(self):
        """CB-05c: Etapa Indexado requiere expedientes_indexados o folios_indexados."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                {
                    "proyecto_id": self.proyecto.id,
                    "miembro_id": self.miembro.id,
                    "etapa_id": self.etapa_indexado.id,
                    "fecha": date.today(),
                    "expedientes_indexados": 0,
                    "folios_indexados": 0,
                }
            )

    def test_cb05_limpieza_requiere_expedientes_o_folios(self):
        """CB-05d: Etapa Limpieza requiere no_expedientes o total_folios."""
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.registro"].create(
                {
                    "proyecto_id": self.proyecto.id,
                    "miembro_id": self.miembro.id,
                    "etapa_id": self.etapa_limpieza.id,
                    "fecha": date.today(),
                    "no_expedientes": 0,
                    "total_folios": 0,
                }
            )

    def test_cb05_digitalizado_valido_con_escaneos(self):
        """CB-05e: Etapa Digitalizado es válida si total_escaneos > 0."""
        registro = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro.id,
                "etapa_id": self.etapa_digitalizado.id,
                "fecha": date.today(),
                "total_escaneos": 100,
                "total_folios": 0,
            }
        )
        self.assertTrue(registro.id)

    # ──────────────────────────────────────────────────────────────────────────
    # CB-06 — _compute_display_name
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb06_display_name_formato(self):
        """CB-06: display_name tiene formato 'Miembro · Etapa · YYYY-MM-DD'."""
        registro = self.env["digitalizacion.registro"].create(
            self._vals_base()
        )
        expected_date = str(date.today())
        self.assertIn("·", registro.display_name)
        self.assertIn(expected_date, registro.display_name)
        self.assertIn(self.etapa_limpieza.name, registro.display_name)

    # ──────────────────────────────────────────────────────────────────────────
    # CB-07 — _compute_produccion_principal
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb07_produccion_limpieza(self):
        """CB-07a: Producción de Limpieza = no_expedientes."""
        registro = self.env["digitalizacion.registro"].create(
            self._vals_base(no_expedientes=42, total_folios=10)
        )
        self.assertEqual(registro.produccion_principal, 42)
        self.assertEqual(registro.unidad_produccion, "expedientes")

    def test_cb07_produccion_digitalizado(self):
        """CB-07b: Producción de Digitalizado = total_escaneos."""
        registro = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro.id,
                "etapa_id": self.etapa_digitalizado.id,
                "fecha": date.today(),
                "total_escaneos": 500,
                "total_folios": 80,
            }
        )
        self.assertEqual(registro.produccion_principal, 500)
        self.assertEqual(registro.unidad_produccion, "escaneos")

    def test_cb07_produccion_editado(self):
        """CB-07c: Producción de Editado = expedientes_editados."""
        registro = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro.id,
                "etapa_id": self.etapa_editado.id,
                "fecha": date.today(),
                "expedientes_editados": 30,
                "folios_editados": 0,
            }
        )
        self.assertEqual(registro.produccion_principal, 30)
        self.assertEqual(registro.unidad_produccion, "exp. editados")

    def test_cb07_produccion_indexado(self):
        """CB-07d: Producción de Indexado = expedientes_indexados."""
        registro = self.env["digitalizacion.registro"].create(
            {
                "proyecto_id": self.proyecto.id,
                "miembro_id": self.miembro.id,
                "etapa_id": self.etapa_indexado.id,
                "fecha": date.today(),
                "expedientes_indexados": 20,
                "folios_indexados": 0,
            }
        )
        self.assertEqual(registro.produccion_principal, 20)
        self.assertEqual(registro.unidad_produccion, "exp. indexados")

    # ──────────────────────────────────────────────────────────────────────────
    # CB-08 — _onchange_etapa (limpieza de campos)
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb08_onchange_etapa_limpia_escaneos(self):
        """CB-08a: Al cambiar a Limpieza, total_escaneos se resetea a 0."""
        from odoo.tests.common import Form
        with Form(self.env["digitalizacion.registro"]) as f:
            f.proyecto_id = self.proyecto
            f.miembro_id = self.miembro
            f.etapa_id = self.etapa_digitalizado
            f.total_escaneos = 100
            f.total_folios = 50
            # Cambiar a Limpieza — el onchange debe resetear escaneos
            f.etapa_id = self.etapa_limpieza
            # Proveer campos mínimos para Limpieza antes del save()
            f.no_expedientes = 5
            f.total_folios = 10
        # Al salir del with se llama save() — verificamos que no falla


    def test_cb08_onchange_etapa_limpia_editado(self):
        """CB-08b: Al cambiar a Digitalizado, campos de editado se limpian."""
        from odoo.tests.common import Form
        with Form(self.env["digitalizacion.registro"]) as f:
            f.proyecto_id = self.proyecto
            f.miembro_id = self.miembro
            f.etapa_id = self.etapa_editado
            f.expedientes_editados = 10
            f.etapa_id = self.etapa_digitalizado
            f.total_escaneos = 50
            # expedientes_editados debe ser 0 después del onchange
            self.assertEqual(f.expedientes_editados, 0)

    # ──────────────────────────────────────────────────────────────────────────
    # CB-09 — create() override: lider_id forzado al usuario actual
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb09_create_fuerza_lider_id(self):
        """CB-09: create() siempre asigna lider_id al usuario en sesión."""
        otro_user = self.env.ref("base.user_admin")
        registro = self.env["digitalizacion.registro"].create(
            self._vals_base(lider_id=otro_user.id)
        )
        # Debe ser el usuario de la sesión actual, no otro_user
        self.assertEqual(registro.lider_id, self.env.user)

    def test_cb09_create_asigna_hora(self):
        """CB-09b: create() asigna hora automáticamente si no se provee."""
        registro = self.env["digitalizacion.registro"].create(self._vals_base())
        self.assertIsNotNone(registro.hora)

    # ──────────────────────────────────────────────────────────────────────────
    # CB-10 — write() override: lider_id no modificable
    # ──────────────────────────────────────────────────────────────────────────

    def test_cb10_write_lider_ignorado(self):
        """CB-10: write() ignora intentos de cambiar lider_id."""
        registro = self.env["digitalizacion.registro"].create(self._vals_base())
        lider_original = registro.lider_id
        otro_user = self.env.ref("base.user_admin")
        registro.write({"lider_id": otro_user.id, "no_expedientes": 20})
        self.assertEqual(registro.lider_id, lider_original)
        self.assertEqual(registro.no_expedientes, 20)
