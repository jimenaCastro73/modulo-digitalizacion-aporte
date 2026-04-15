# -*- coding: utf-8 -*-
"""
asignacion.py — Modelo: digitalizacion.asignacion
Tabla T-04 · Asignación de Líder a Proyecto

Gestiona la relación entre un usuario Odoo con rol de Líder (res.users)
y un proyecto de digitalización.

Restricciones de negocio:
  - UNIQUE(lider_id, proyecto_id).
  - El líder puede rotar entre proyectos (múltiples asignaciones activas).
  - SOLO el admin puede crear/asignar líderes.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DigitalizacionAsignacion(models.Model):
    _name = "digitalizacion.asignacion"
    _description = "Asignación de Líder a Proyecto"
    _order = "fecha_asignacion desc, proyecto_id asc"

    _sql_constraints = [
        (
            "unique_asignacion_lider",
            "UNIQUE(lider_id, proyecto_id)",
            "Este líder ya está asignado al proyecto seleccionado.",
        ),
    ]

    # Campos

    lider_id = fields.Many2one(
        comodel_name="res.users",
        string="Líder",
        required=True,
        ondelete="restrict",
        domain="[('share', '=', True), ('active', '=', True)]",
        help="Usuario portal con rol de Líder.",
    )

    proyecto_id = fields.Many2one(
        comodel_name="digitalizacion.proyecto",
        string="Proyecto",
        required=True,
        ondelete="restrict",
        domain="[('active', '=', True)]",
    )

    fecha_asignacion = fields.Date(
        string="Fecha de asignación",
        default=fields.Date.today,
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete. False = el líder pierde acceso al proyecto en el portal.",
    )

    # Campo computado de nombre

    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=False,
    )

    # Restricciones Python

    @api.constrains("lider_id", "proyecto_id")
    def _check_lider_tiene_grupo(self):
        """
        Verifica que el usuario asignado pertenezca al grupo de Líder.

        Regla de negocio: solo un usuario con el grupo correcto puede
        acceder al portal de digitalización.
        """
        grupo_lider = self.env.ref(
            "digitalizacion.group_digitalizacion_lider",
            raise_if_not_found=False,
        )

        if not grupo_lider:
            return

        for record in self:
            lider_tiene_grupo = grupo_lider in record.lider_id.groups_id
            if not lider_tiene_grupo:
                raise ValidationError(
                    _(
                        "El usuario '%s' no pertenece al grupo "
                        "'Digitalización / Líder'. Verifica sus permisos antes de asignar.",
                        record.lider_id.name,
                    )
                )

    @api.constrains("fecha_asignacion")
    def _check_fecha_asignacion(self):
        """La fecha de asignación no puede ser futura."""
        hoy = fields.Date.today()
        for record in self:
            if record.fecha_asignacion and record.fecha_asignacion > hoy:
                raise ValidationError(
                    _(
                        "La fecha de asignación (%s) no puede ser futura.",
                        record.fecha_asignacion,
                    )
                )

    # Métodos computados

    @api.depends("lider_id", "proyecto_id")
    def _compute_display_name(self):
        for record in self:
            lider = record.lider_id.name or "Sin líder"
            proyecto = record.proyecto_id.name or "Sin proyecto"
            record.display_name = f"{lider} → {proyecto}"

    # Overrides CRUD

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea asignaciones con patrón reactivar-si-existe, crear-si-no-existe.
        ELIMINADO: ya no crea miembro_proyecto automáticamente.
        """
        registros_a_crear = []

        for vals in vals_list:
            asignacion_archivada = self.with_context(active_test=False).search(
                [
                    ("lider_id", "=", vals.get("lider_id")),
                    ("proyecto_id", "=", vals.get("proyecto_id")),
                    ("active", "=", False),
                ],
                limit=1,
            )

            if asignacion_archivada:
                asignacion_archivada.write(
                    {
                        "active": True,
                        "fecha_asignacion": vals.get(
                            "fecha_asignacion", fields.Date.today()
                        ),
                    }
                )
            else:
                registros_a_crear.append(vals)

        if registros_a_crear:
            return super().create(registros_a_crear)
        return self.env["digitalizacion.asignacion"]

    def write(self, vals):
        """
        Al reactivar una asignación (active=True), ya NO crea miembro_proyecto.
        """
        return super().write(vals)

    # Acciones

    def action_desactivar(self):
        """Desactiva la asignación."""
        self.write({"active": False})

    def action_activar(self):
        """Reactiva la asignación."""
        self.write({"active": True})
