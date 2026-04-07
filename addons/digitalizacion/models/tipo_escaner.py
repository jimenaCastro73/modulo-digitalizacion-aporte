# -*- coding: utf-8 -*-
"""
tipo_escaner.py — Modelo: digitalizacion.tipo_escaner
Tabla T-02 · Catálogo global de tipos de escáneres
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("name")
    def _check_name(self):
        """
        El nombre del tipo de escáner debe identificar claramente el equipo.

        No se aceptan nombres vacíos ni solo numéricos porque
        impedirían identificar visualmente el equipo en los reportes.
        """
        for record in self:
            nombre = (record.name or "").strip()

            if not nombre:
                raise ValidationError(
                    _("El nombre del tipo de escáner no puede estar vacío.")
                )

            solo_numeros = nombre.isdigit()
            if solo_numeros:
                raise ValidationError(
                    _(
                        "El nombre del escáner no puede ser solo números: '%s'. "
                        "Usa el modelo o marca. Ej: 'Fujitsu fi-7300NX'.",
                        nombre,
                    )
                )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("name")
    def _compute_registro_count(self):
        """
        Cuenta los registros en los que se usó este tipo de escáner.

        Usa _read_group para evitar N queries — una sola consulta
        agrupa todos los registros del recordset en una sola ida a la BD.
        """
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
        }

