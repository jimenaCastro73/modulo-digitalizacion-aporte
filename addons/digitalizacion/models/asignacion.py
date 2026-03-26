# -*- coding: utf-8 -*-
"""
asignacion.py — Modelo: digitalizacion.asignacion
Tabla T-04 · Asignación de Líder a Proyecto

Gestiona la relación entre un usuario Odoo con rol de Líder (res.users)
y un proyecto de digitalización.

Restricciones de negocio:
  - UNIQUE(lider_id, proyecto_id).
  - El líder puede rotar entre proyectos (múltiples asignaciones activas).

Efecto secundario en create/write:
  Al crear una asignación, el sistema crea automáticamente el registro
  en digitalizacion.miembro_proyecto (T-05) para que el Líder aparezca
  en el selector de digitalizadores del formulario.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Asignacion(models.Model):
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

    # ── Campos ────────────────────────────────────────────────────────────────

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

    # ── Campo computado de nombre ─────────────────────────────────────────────

    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=False,
    )

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("lider_id", "proyecto_id")
    def _check_lider_tiene_grupo(self):
        """Verifica que el usuario asignado pertenezca al grupo de Líder."""
        grupo_lider = self.env.ref(
            "digitalizacion.group_digitalizacion_lider",
            raise_if_not_found=False,
        )
        if not grupo_lider:
            return

        for record in self:
            if grupo_lider not in record.lider_id.groups_id:
                raise ValidationError(
                    _(
                        "El usuario '%s' no pertenece al grupo "
                        "'Digitalización / Líder'. Verifica sus permisos antes de asignar.",
                        record.lider_id.name,
                    )
                )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("lider_id", "proyecto_id")
    def _compute_display_name(self):
        for record in self:
            lider = record.lider_id.name or "Sin líder"
            proyecto = record.proyecto_id.name or "Sin proyecto"
            record.display_name = f"{lider} → {proyecto}"

    # ── Overrides CRUD ────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """
        Al crear una asignación:
        - Si existe una archivada para el mismo líder+proyecto, la reactiva.
        - Crea automáticamente el miembro_proyecto del líder.
        """
        records_to_create = []
        created = self.env["digitalizacion.asignacion"]

        for vals in vals_list:
            existente = self.with_context(active_test=False).search(
                [
                    ("lider_id", "=", vals.get("lider_id")),
                    ("proyecto_id", "=", vals.get("proyecto_id")),
                    ("active", "=", False),
                ],
                limit=1,
            )

            if existente:
                existente.write(
                    {
                        "active": True,
                        "fecha_asignacion": vals.get(
                            "fecha_asignacion", fields.Date.today()
                        ),
                    }
                )
                created |= existente
            else:
                records_to_create.append(vals)

        if records_to_create:
            created |= super().create(records_to_create)

        for asig in created:
            self._crear_miembro_para_lider(asig)

        return created

    def write(self, vals):
        """Si se reactiva una asignación, verifica que el miembro_proyecto también esté activo."""
        result = super().write(vals)
        if vals.get("active") is True:
            for asig in self:
                self._crear_miembro_para_lider(asig)
        return result

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _crear_miembro_para_lider(self, asignacion):
        """
        Crea o reactiva el registro digitalizacion.miembro_proyecto
        correspondiente al líder para el proyecto dado.
        """
        Miembro = self.env["digitalizacion.miembro_proyecto"].sudo()
        partner = asignacion.lider_id.partner_id

        if not partner:
            _logger.warning(
                "El líder '%s' (ID %d) no tiene partner_id asociado. "
                "No se creó miembro_proyecto automáticamente.",
                asignacion.lider_id.name,
                asignacion.lider_id.id,
            )
            return

        miembro_existente = Miembro.with_context(active_test=False).search(
            [
                ("proyecto_id", "=", asignacion.proyecto_id.id),
                ("partner_id", "=", partner.id),
            ],
            limit=1,
        )

        if miembro_existente:
            if not miembro_existente.active:
                miembro_existente.write({"active": True, "fecha_salida": False})
                _logger.info(
                    "Miembro_proyecto reactivado para líder '%s' en proyecto '%s'.",
                    asignacion.lider_id.name,
                    asignacion.proyecto_id.name,
                )
        else:
            Miembro.create(
                {
                    "proyecto_id": asignacion.proyecto_id.id,
                    "partner_id": partner.id,
                    "fecha_integracion": asignacion.fecha_asignacion
                    or fields.Date.today(),
                    "active": True,
                }
            )
            _logger.info(
                "Miembro_proyecto creado para líder '%s' en proyecto '%s'.",
                asignacion.lider_id.name,
                asignacion.proyecto_id.name,
            )

    # ── Acciones ──────────────────────────────────────────────────────────────

    def action_desactivar(self):
        """Desactiva la asignación."""
        self.write({"active": False})

    def action_activar(self):
        """Reactiva la asignación."""
        self.write({"active": True})
