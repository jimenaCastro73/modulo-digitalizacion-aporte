# -*- coding: utf-8 -*-
"""
tipo_escaner.py — Modelo: digitalizacion.tipo_escaner
Tabla T-02 · Catálogo global de tipos de escáneres
"""

from odoo import _, fields, models

from .mixins import _NombreValidoMixin


class DigitalizacionTipoEscaner(_NombreValidoMixin, models.Model):
    _name = "digitalizacion.tipo_escaner"
    _description = "Tipo de Escáner"
    _order = "name asc"
    _inherit = ["digitalizacion.mixin.nombre_valido"]

    # Personaliza el mensaje del mixin _check_name
    _nombre_objeto = _("el tipo de escáner")

    _sql_constraints = [
        (
            "unique_tipo_escaner_name",
            "UNIQUE(name)",
            "Ya existe un tipo de escáner con ese nombre.",
        ),
    ]

    # Campos

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

    # Métodos de acción

    def action_ver_registros(self):
        """Abre los registros donde se usó este tipo de escáner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registros de producción — %s", self.name),
            "res_model": "digitalizacion.registro",
            "view_mode": "tree,form",
            "domain": [("tipo_escaner_ids", "in", self.id)],
            "context": {"default_tipo_escaner_ids": [(4, self.id)]},
            "target": "current",
        }