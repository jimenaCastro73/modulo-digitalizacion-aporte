# -*- coding: utf-8 -*-
"""
etapa.py — Modelo: digitalizacion.etapa
Tabla T-01 · Catálogo de etapas del proceso de digitalización

Tabla de datos maestros administrada por el Administrador. Define las etapas
disponibles (Limpieza, Digitalizado, Editado, Indexado, Ordenado) y permite
agregar nuevas sin modificar código, evitando campos hardcodeados.

Referenciada por digitalizacion.registro mediante el campo etapa_id (Many2one).
La visibilidad dinámica de los campos del formulario depende del nombre de la
etapa (etapa_id.name), evaluado en la vista QWeb del portal.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DigitalizacionEtapa(models.Model):
    _name = "digitalizacion.etapa"
    _description = "Etapa de Digitalización"
    _order = "sequence asc, name asc"

    # ── Campos ────────────────────────────────────────────────────────────────

    name = fields.Char(
        string="Nombre",
        required=True,
        help="Nombre de la etapa. Ej: Limpieza, Digitalizado, Editado, "
        "Indexado, Ordenado.",
    )

    sequence = fields.Integer(
        string="Secuencia",
        default=10,
        help="Orden de visualización en listas y vistas. "
        "Permite reordenar sin alterar datos.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete de Odoo. False = etapa archivada/inactiva. "
        "No aparece en el formulario de registro.",
    )

    # ── Campo computado: cantidad de registros que usan esta etapa ────────────

    registro_count = fields.Integer(
        string="Registros",
        compute="_compute_registro_count",
        store=False,
        help="Cantidad de registros de trabajo asociados a esta etapa.",
    )

    # ── Restricciones SQL ─────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "unique_etapa_name",
            "UNIQUE(name)",
            "Ya existe una etapa con ese nombre.",
        ),
    ]

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("name")
    def _check_name_not_empty(self):
        for rec in self:
            if not rec.name or not rec.name.strip():
                raise ValidationError("El nombre de la etapa no puede estar vacío.")

    # ── Métodos computados ────────────────────────────────────────────────────

    # No @api.depends: se recalcula al leer (sin trigger específico)
    def _compute_registro_count(self):
        """
        Cuenta los registros de trabajo asociados a cada etapa.
        Usado en la vista de lista del backoffice para referencia del Administrador.
        Optimizado con _read_group para evitar N+1 queries.
        """
        Registro = self.env["digitalizacion.registro"]
        if not self.ids:
            return
        datos = Registro._read_group(
            domain=[("etapa_id", "in", self.ids)],
            groupby=["etapa_id"],
            aggregates=["__count"],
        )
        conteos = {etapa.id: count for etapa, count in datos}
        for etapa in self:
            etapa.registro_count = conteos.get(etapa.id, 0)

    # ── Métodos de acción ─────────────────────────────────────────────────────

    def action_ver_registros(self):
        """
        Acción del botón 'Ver registros' en la vista de formulario del backend.
        Abre la lista de registros filtrada por esta etapa.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Registros — {self.name}",
            "res_model": "digitalizacion.registro",
            "view_mode": "list,form",
            "domain": [("etapa_id", "=", self.id)],
            "context": {"default_etapa_id": self.id},
        }
