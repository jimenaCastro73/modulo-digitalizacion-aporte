# -*- coding: utf-8 -*-
"""
etapa.py — Modelo: digitalizacion.etapa
Tabla T-01 · Catálogo de etapas del proceso de digitalización
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .mixins import _NombreValidoMixin


class DigitalizacionEtapa(_NombreValidoMixin, models.Model):
    _name = "digitalizacion.etapa"
    _description = "Etapa de Digitalización"
    _order = "sequence asc, name asc"
    _inherit = ["digitalizacion.mixin.nombre_valido"]

    # Personaliza el mensaje del mixin _check_name
    _nombre_objeto = _("la etapa")

    _sql_constraints = [
        (
            "unique_etapa_name",
            "UNIQUE(name)",
            "Ya existe una etapa con ese nombre.",
        ),
    ]

    # Campos

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

    # Restricciones Python

    @api.constrains("sequence")
    def _check_sequence(self):
        """La secuencia debe ser un número positivo o cero (no negativo)."""
        for record in self:
            if record.sequence < 0:
                raise ValidationError(
                    _(
                        "La secuencia no puede ser negativa (valor actual: %d).",
                        record.sequence,
                    )
                )

        # Métodos de acción

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
