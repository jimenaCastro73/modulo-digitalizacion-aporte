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
        """
        Verifica que el usuario asignado pertenezca al grupo de Líder.

        Regla de negocio: solo un usuario con el grupo correcto puede
        acceder al portal de digitalización. Asignar un usuario sin ese
        grupo resultaría en un portal vacío o errores de acceso.
        """
        grupo_lider = self.env.ref(
            "digitalizacion.group_digitalizacion_lider",
            raise_if_not_found=False,
        )

        # Si el grupo no existe (ej: módulo parcialmente instalado), no validar
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
        """
        La fecha de asignación no puede ser futura.

        Regla de negocio: las asignaciones son hechos ya ocurridos.
        """
        hoy = fields.Date.today()
        for record in self:
            fecha_es_futura = record.fecha_asignacion and record.fecha_asignacion > hoy
            if fecha_es_futura:
                raise ValidationError(
                    _(
                        "La fecha de asignación (%s) no puede ser futura.",
                        record.fecha_asignacion,
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
        Crea asignaciones con patrón reactivar-si-existe, crear-si-no-existe.

        Antes de crear un nuevo registro, verifica si ya existe uno archivado
        (active=False) para el mismo líder + proyecto. Si existe, lo reactiva
        en lugar de crear un duplicado (respetando la constraint UNIQUE).

        Efecto secundario: tras crear/reactivar la asignación, llama a
        _crear_miembro_para_lider() para que el líder también aparezca
        como digitalizador en el selector del formulario.
        """
        registros_a_crear = []
        registros_procesados = self.env["digitalizacion.asignacion"]

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
                # Reactivar en lugar de crear un duplicado
                asignacion_archivada.write(
                    {
                        "active": True,
                        "fecha_asignacion": vals.get(
                            "fecha_asignacion", fields.Date.today()
                        ),
                    }
                )
                registros_procesados |= asignacion_archivada
            else:
                registros_a_crear.append(vals)

        if registros_a_crear:
            registros_procesados |= super().create(registros_a_crear)

        for asig in registros_procesados:
            self._crear_miembro_para_lider(asig)

        return registros_procesados

    def write(self, vals):
        """
        Al reactivar una asignación (active=True), verifica que el
        miembro_proyecto del líder también esté activo en ese proyecto.
        """
        resultado = super().write(vals)

        reactivando_asignacion = vals.get("active") is True
        if reactivando_asignacion:
            for asig in self:
                self._crear_miembro_para_lider(asig)

        return resultado

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
