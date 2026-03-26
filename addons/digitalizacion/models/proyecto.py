# -*- coding: utf-8 -*-
"""
proyecto.py — Modelo: digitalizacion.proyecto
Tabla T-03 · Registro central de proyectos de digitalización
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Proyecto(models.Model):
    _name = "digitalizacion.proyecto"
    _description = "Proyecto de Digitalización"
    _order = "fecha_inicio desc, name asc"

    _sql_constraints = [
        (
            "unique_proyecto_name",
            "UNIQUE(name)",
            "Ya existe un proyecto con ese nombre.",
        ),
    ]

    # ── Campos principales ────────────────────────────────────────────────────

    name = fields.Char(
        string="Nombre",
        required=True,
        help="Nombre descriptivo del proyecto. Ej: Imprema 2026, Centro Cívico.",
    )

    description = fields.Text(
        string="Descripción",
        help="Detalle adicional del alcance o contexto del proyecto.",
    )

    fecha_inicio = fields.Date(
        string="Fecha de inicio",
        required=True,
        default=fields.Date.today,
    )

    fecha_fin_estimada = fields.Date(
        string="Fecha fin estimada",
        help="Fecha estimada de finalización.",
    )

    duracion_estimada = fields.Integer(
        string="Duración estimada (días)",
        compute="_compute_duracion_estimada",
        store=True,
        help="Días entre fecha_inicio y fecha_fin_estimada.",
    )

    state = fields.Selection(
        string="Estado",
        selection=[
            ("activo", "Activo"),
            ("inactivo", "Inactivo"),
        ],
        required=True,
        default="activo",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete de Odoo. False = proyecto archivado.",
    )

    color = fields.Integer(
        string="Color Index",
        help="Color para la vista Kanban.",
    )

    meta_escaneos = fields.Integer(
        string="Meta de escaneos",
        default=0,
        help="Cantidad objetivo de escaneos para este proyecto.",
    )

    # ── Relaciones inversas ───────────────────────────────────────────────────

    asignacion_ids = fields.One2many(
        comodel_name="digitalizacion.asignacion",
        inverse_name="proyecto_id",
        string="Asignaciones de Líder",
    )

    miembro_ids = fields.One2many(
        comodel_name="digitalizacion.miembro_proyecto",
        inverse_name="proyecto_id",
        string="Miembros del equipo",
    )

    registro_ids = fields.One2many(
        comodel_name="digitalizacion.registro",
        inverse_name="proyecto_id",
        string="Registros de trabajo",
    )

    # ── Campos computados ─────────────────────────────────────────────────────

    lider_ids = fields.Many2many(
        comodel_name="res.users",
        string="Líderes",
        compute="_compute_lider_ids",
        store=False,
        help="Usuarios asignados como líderes activos del proyecto.",
    )

    total_miembros = fields.Integer(
        string="Total miembros",
        compute="_compute_totales",
        store=True,
    )

    total_registros = fields.Integer(
        string="Total registros",
        compute="_compute_totales",
        store=True,
    )

    total_escaneos = fields.Integer(
        string="Total escaneos",
        compute="_compute_totales",
        store=True,
        help="Suma acumulada de escaneos en todos los registros del proyecto.",
    )

    progreso = fields.Float(
        string="Progreso (%)",
        compute="_compute_progreso",
        store=True,
        digits=(5, 1),
        help="Porcentaje: (escaneos / meta) × 100.",
    )

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("fecha_inicio", "fecha_fin_estimada")
    def _check_fechas(self):
        for record in self:
            if record.fecha_fin_estimada and record.fecha_inicio:
                if record.fecha_fin_estimada < record.fecha_inicio:
                    raise ValidationError(
                        _(
                            "La fecha de fin estimada no puede ser anterior "
                            "a la fecha de inicio."
                        )
                    )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("fecha_inicio", "fecha_fin_estimada")
    def _compute_duracion_estimada(self):
        # El campo compute con store=True ya actualiza en el formulario
        # automáticamente. No se necesita @api.onchange adicional.
        for record in self:
            if record.fecha_inicio and record.fecha_fin_estimada:
                record.duracion_estimada = (record.fecha_fin_estimada - record.fecha_inicio).days
            else:
                record.duracion_estimada = 0

    @api.depends("asignacion_ids", "asignacion_ids.active")
    def _compute_lider_ids(self):
        for proyecto in self:
            proyecto.lider_ids = proyecto.asignacion_ids.filtered(
                lambda a: a.active
            ).mapped("lider_id")

    @api.depends("miembro_ids", "registro_ids", "registro_ids.total_escaneos")
    def _compute_totales(self):
        for proyecto in self:
            proyecto.total_miembros = len(proyecto.miembro_ids.filtered("active"))
            proyecto.total_registros = len(proyecto.registro_ids)
            proyecto.total_escaneos = sum(
                record.total_escaneos or 0 for record in proyecto.registro_ids
            )

    @api.depends("total_escaneos", "meta_escaneos")
    def _compute_progreso(self):
        for proyecto in self:
            if proyecto.meta_escaneos and proyecto.meta_escaneos > 0:
                proyecto.progreso = min(
                    (proyecto.total_escaneos / proyecto.meta_escaneos) * 100.00,
                    100.00,
                )
            else:
                proyecto.progreso = 0.00

    # ── Métodos de negocio ────────────────────────────────────────────────────

    def action_archivar(self):
        """Archiva el proyecto y desactiva asignaciones y líderes."""
        for proyecto in self:
            lideres = proyecto.miembro_ids.filtered(lambda m: m.es_lider and m.active)
            if lideres:
                lideres.write({"es_lider": False})
            proyecto.asignacion_ids.filtered("active").write({"active": False})
            proyecto.active = False

    def action_activar(self):
        """Reactiva un proyecto archivado."""
        for proyecto in self:
            proyecto.write({"active": True, "state": "activo"})

            # Reactivar miembros sin fecha_salida (búsqueda fuera del loop)
        miembros_inactivos = (
            self.env["digitalizacion.miembro_proyecto"]
            .with_context(active_test=False)
            .search(
                [
                    ("proyecto_id", "in", self.ids),
                    ("active", "=", False),
                    ("fecha_salida", "=", False),
                ]
            )
        )
        if miembros_inactivos:
            miembros_inactivos.write({"active": True})

        for proyecto in self:
            lideres_activos = proyecto.miembro_ids.filtered(
                lambda m: m.es_lider and m.active
            )
            for lider_miembro in lideres_activos:
                lider_miembro._sincronizar_liderazgo(True)

    def action_inactivar(self):
        """Cambia el estado a inactivo sin archivar."""
        self.write({"state": "inactivo"})

    def action_ver_registros(self):
        """Abre la lista de registros filtrada por este proyecto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registros — %s", self.name),
            "res_model": "digitalizacion.registro",
            "view_mode": "tree,form",
            "domain": [("proyecto_id", "=", self.id)],
            "context": {"default_proyecto_id": self.id},
            "target": "current",
        }

    def action_ver_miembros(self):
        """Abre la lista de miembros del equipo de este proyecto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Equipo — %s", self.name),
            "res_model": "digitalizacion.miembro_proyecto",
            "view_mode": "tree,form",
            "domain": [("proyecto_id", "=", self.id)],
            "context": {"default_proyecto_id": self.id},
            "target": "current",
        }
