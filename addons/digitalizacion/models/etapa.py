# -*- coding: utf-8 -*-
"""
etapa.py — Modelo: digitalizacion.etapa
Tabla T-01 · Catálogo de etapas del proceso de digitalización
"""

import re

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
    def _check_name(self):
        for record in self:
            nombre = (record.name or "").strip()
            if not nombre:
                raise ValidationError(_("El nombre de la etapa no puede estar vacío."))
            if nombre.isdigit():
                raise ValidationError(
                    _("El nombre de la etapa no puede ser solo números: '%s'.", nombre)
                )
            if re.fullmatch(r'[^\w\s\-\.áéíóúÁÉÍÓÚüÜñÑ]+', nombre):
                raise ValidationError(
                    _("El nombre de la etapa contiene solo caracteres especiales: '%s'.", nombre)
                )

    @api.constrains("sequence")
    def _check_sequence(self):
        """La secuencia debe ser un número positivo o cero (no negativo)."""
        for record in self:
            tiene_secuencia_negativa = record.sequence < 0
            if tiene_secuencia_negativa:
                raise ValidationError(
                    _("La secuencia no puede ser negativa (valor actual: %d).", record.sequence)
                )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("name")
    def _compute_registro_count(self):
        """
        Cuenta los registros asociados a cada etapa usando una sola query SQL.

        Usa _read_group para evitar N queries — una sola consulta agrupada
        es suficiente para todo el recordset.
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
