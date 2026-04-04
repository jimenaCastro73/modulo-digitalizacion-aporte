# -*- coding: utf-8 -*-
"""
tipo_escaner.py — Modelo: digitalizacion.tipo_escaner
Tabla T-02 · Catálogo global de tipos de escáneres
"""

from odoo import api, fields, models


class DigitalizacionTipoEscaner(models.Model):
    _name = "digitalizacion.tipo_escaner"
    _description = "Tipo de Escáner"
    _order = "name asc"

    _sql_constraints = [
        (
            "unique_tipo_escaner_name",
            "UNIQUE(name)",
            "Ya existe un tipo de escáner con ese nombre.",
        ),
    ]

    # ── Campos ────────────────────────────────────────────────────────────────

    name = fields.Char(
        string="Nombre",
        required=True,
        help="Nombre o modelo del escáner. Ej: Fujitsu fi-7300NX, Epson GT-S85.",
    )

    description = fields.Text(
        string="Descripción",
        help="Descripción adicional del equipo (velocidad, formato, ubicación, etc.).",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete. False = escáner archivado/fuera de uso.",
    )

    registro_count = fields.Integer(
        string="Usos en registros",
        compute="_compute_registro_count",
        store=False,
        help="Cantidad de registros que usan este escáner.",
    )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("name")
    def _compute_registro_count(self):
        """Cuenta usos en registros via _read_group."""
        if not self.ids:
            for record in self:
                record.registro_count = 0
            return
        datos = self.env["digitalizacion.registro"]._read_group(
            domain=[("tipo_escaner_ids", "in", self.ids)],
            groupby=["tipo_escaner_ids"],
            aggregates=["__count"],
        )
        conteos = {escaner.id: count for escaner, count in datos}
        for record in self:
            record.registro_count = conteos.get(record.id, 0)

    def action_view_registros(self):
        self.ensure_one()
        return {
            "name": "Registros de producción (Escáner: %s)" % self.name,
            "type": "ir.actions.act_window",
            "res_model": "digitalizacion.registro",
            "view_mode": "tree,form",
            "domain": [("tipo_escaner_ids", "in", self.id)],
            "context": {"default_tipo_escaner_ids": [(4, self.id)]},
        }
