# -*- coding: utf-8 -*-
"""
etapa.py — Modelo: digitalizacion.etapa
Tabla T-01 · Catálogo de etapas del proceso de digitalización
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DigitalizacionEtapa(models.Model):
    _name = "digitalizacion.etapa"
    _description = "Etapa de Digitalización"
    _order = "sequence asc, name asc"

    _sql_constraints = [
        (
            "unique_etapa_name",
            "UNIQUE(name)",
            "Ya existe una etapa con ese nombre.",
        ),
    ]

    # ── Campos ────────────────────────────────────────────────────────────────

    name = fields.Char(
        string="Nombre",
        required=True,
        help="Nombre de la etapa. Ej: Limpieza, Digitalizado, Editado, Indexado, Ordenado.",
    )

    sequence = fields.Integer(
        string="Secuencia",
        default=10,
        help="Orden de visualización. Permite reordenar sin alterar datos.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete. False = etapa archivada.",
    )

    registro_count = fields.Integer(
        string="Registros",
        compute="_compute_registro_count",
        store=False,
        help="Cantidad de registros asociados a esta etapa.",
    )

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("name")
    def _check_name_not_empty(self):
        for record in self:
            if not record.name or not record.name.strip():
                raise ValidationError(_("El nombre de la etapa no puede estar vacío."))

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("name")
    def _compute_registro_count(self):
        """
        Cuenta registros por etapa. Optimizado con _read_group.
        """
        if not self.ids:
            for etapa in self:
                etapa.registro_count = 0
            return
        datos = self.env["digitalizacion.registro"]._read_group(
            domain=[("etapa_id", "in", self.ids)],
            groupby=["etapa_id"],
            aggregates=["__count"],
        )
        conteos = {etapa.id: count for etapa, count in datos}
        for etapa in self:
            etapa.registro_count = conteos.get(etapa.id, 0)

    # ── Métodos de acción ─────────────────────────────────────────────────────

    def action_ver_registros(self):
        """Abre la lista de registros filtrada por esta etapa."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registros — %s", self.name),
            "res_model": "digitalizacion.registro",
            "view_mode": "tree,form",
            "domain": [("etapa_id", "=", self.id)],
            "context": {"default_etapa_id": self.id},
            "target": "current",
        }
