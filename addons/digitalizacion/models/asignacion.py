# -*- coding: utf-8 -*-
"""
asignacion.py — Modelo: digitalizacion.asignacion
Tabla T-04 · Asignación de Líder a Proyecto

Gestiona la relación entre un usuario Odoo con rol de Líder (res.users)
y un proyecto de digitalización. El Líder es el único usuario Odoo del
equipo: accede al portal, registra la producción diaria de todos los
integrantes (incluido él mismo como digitalizador) y gestiona los miembros.

Restricción de negocio:
  - Un líder no puede estar asignado dos veces al mismo proyecto.
  - UNIQUE(lider_id, proyecto_id).
  - El líder puede rotar entre proyectos (tener múltiples asignaciones activas).

Efecto secundario (override de create/write):
  Al crear una asignación, el sistema crea automáticamente el registro
  correspondiente en digitalizacion.miembro_proyecto (T-05) para que el
  Líder aparezca en el selector de digitalizadores del formulario.
  (Nota 3.8 de la documentación técnica)
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Asignacion(models.Model):
    _name = "digitalizacion.asignacion"
    _description = "Asignación de Líder a Proyecto"
    _order = "fecha_asignacion desc, proyecto_id asc"
    _rec_name = "display_name"

    # ── Campos ────────────────────────────────────────────────────────────────

    lider_id = fields.Many2one(
        comodel_name="res.users",
        string="Líder",
        required=True,
        ondelete="restrict",
        domain="[('share', '=', True), ('active', '=', True)]",
        help="Usuario Odoo con rol de Líder (grupo Digitalización / Líder). "
        "Accede al portal y registra la producción del equipo.",
    )

    proyecto_id = fields.Many2one(
        comodel_name="digitalizacion.proyecto",
        string="Proyecto",
        required=True,
        ondelete="restrict",
        domain="[('active', '=', True)]",
        help="Proyecto al que se asigna el líder.",
    )

    fecha_asignacion = fields.Date(
        string="Fecha de asignación",
        default=fields.Date.today,
        help="Fecha en que se realizó la asignación del líder al proyecto.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete. False = el líder pierde acceso al proyecto en el portal.",
    )

    # ── Campo computado de nombre para _rec_name ──────────────────────────────

    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=False,
    )

    # ── Restricciones SQL ─────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "unique_asignacion_lider",
            "UNIQUE(lider_id, proyecto_id)",
            "Este líder ya está asignado al proyecto seleccionado.",
        ),
    ]

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains('proyecto_id', 'lider_id')
    def _check_lider_unico_por_proyecto(self):
        for rec in self:
            duplicado = self.search([
                ('proyecto_id', '=', rec.proyecto_id.id),
                ('lider_id', '=', rec.lider_id.id),
                ('id', '!=', rec.id)
            ])
            if duplicado:
                raise ValidationError(
                    "Este líder ya está asignado a este proyecto."
                )

    @api.constrains("lider_id", "proyecto_id")
    def _check_lider_tiene_grupo(self):
        """
        Verifica que el usuario asignado como líder pertenezca al grupo correcto.
        Previene asignar usuarios sin el rol portal de digitalización.
        """
        grupo_lider = self.env.ref(
            "digitalizacion.group_digitalizacion_lider",
            raise_if_not_found=False,
        )
        if not grupo_lider:
            return  # Si el grupo aún no existe (instalación inicial), omitir

        for rec in self:
            if grupo_lider not in rec.lider_id.groups_id:
                raise ValidationError(
                    f"El usuario '{rec.lider_id.name}' no pertenece al grupo "
                    f"'Digitalización / Líder'. Verifica sus permisos antes de asignar."
                )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("lider_id", "proyecto_id")
    def _compute_display_name(self):
        for rec in self:
            lider = rec.lider_id.name or "Sin líder"
            proyecto = rec.proyecto_id.name or "Sin proyecto"
            rec.display_name = f"{lider} → {proyecto}"

    # ── Override create: auto-crear miembro_proyecto para el líder ────────────

    @api.model_create_multi
    def create(self, vals_list):
        """
        Al crear una asignación, crea automáticamente el registro en
        digitalizacion.miembro_proyecto para que el Líder aparezca como
        digitalizador disponible en el formulario de registro.

        Nota 3.8: Si ya existe un miembro_proyecto para ese (proyecto, partner),
        no se duplica (respeta la restricción UNIQUE).
        """
        records = super().create(vals_list)

        for asig in records:
            self._crear_miembro_para_lider(asig)

        return records

    def write(self, vals):
        """
        Si se reactiva una asignación (active: False → True), verifica que
        el miembro_proyecto del líder también esté activo.
        """
        result = super().write(vals)

        if vals.get("active") is True:
            for asig in self:
                self._crear_miembro_para_lider(asig)

        return result

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _crear_miembro_para_lider(self, asignacion):
        """
        Crea (o reactiva) el registro digitalizacion.miembro_proyecto
        correspondiente al líder para el proyecto dado.

        Lógica:
          1. Buscar miembro_proyecto existente (activo o archivado).
          2. Si existe y está inactivo → reactivar.
          3. Si no existe → crear.
          4. Si ya existe y activo → no hacer nada (UNIQUE garantiza integridad).
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

        # Buscar incluyendo archivados (active_test=False)
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
                "Miembro_proyecto creado automáticamente para líder '%s' en proyecto '%s'.",
                asignacion.lider_id.name,
                asignacion.proyecto_id.name,
            )

    # ── Acciones ──────────────────────────────────────────────────────────────

    def action_desactivar(self):
        """Desactiva la asignación: el líder pierde acceso al proyecto en el portal."""
        self.write({"active": False})

    def action_activar(self):
        """Reactiva la asignación."""
        self.write({"active": True})
