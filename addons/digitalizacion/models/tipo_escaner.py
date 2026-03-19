# -*- coding: utf-8 -*-
"""
tipo_escaner.py — Modelo: digitalizacion.tipo_escaner
Tabla T-02 · Catálogo global de tipos de escáneres

Catálogo compartido por todos los proyectos. Permite registrar el equipo
utilizado durante la etapa de Digitalizado. Referenciado desde
digitalizacion.registro mediante el campo Many2many tipo_escaner_ids.
"""

from odoo import fields, models


class DigitalizacionTipoEscaner(models.Model):
    _name = "digitalizacion.tipo_escaner"
    _description = "Tipo de Escáner"
    _order = "name asc"

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
        help="Soft delete de Odoo. False = escáner archivado/fuera de uso. "
        "No aparece en el formulario de registro.",
    )

    # ── Restricciones SQL ─────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "unique_tipo_escaner_name",
            "UNIQUE(name)",
            "Ya existe un tipo de escáner con ese nombre.",
        ),
    ]
