# -*- coding: utf-8 -*-
"""
proyecto.py — Modelo: digitalizacion.proyecto
Tabla T-03 · Registro central de proyectos de digitalización
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DigitalizacionProyecto(models.Model):
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

    # Campos principales

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

    duracion_estimada = fields.Float(
        string="Duración estimada (días)",
        compute="_compute_duracion_estimada",
        store=True,
        group_operator="sum",
        help="Días entre fecha_inicio y fecha_fin_estimada.",
    )

    state = fields.Selection(
        string="Estado",
        selection=[
            ("en_curso", "En curso"),
            ("pausado", "Pausa / Standby"),
            ("finalizado", "Finalizado"),
        ],
        required=True,
        default="en_curso",
        help="Estado del proyecto: En curso (activo), Pausado (standby) o Finalizado.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete de Odoo. False = proyecto archivado.",
    )

    # Relaciones inversas

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

    # Campos computados

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
        group_operator="sum",
    )

    total_registros = fields.Integer(
        string="Total registros",
        compute="_compute_totales",
        store=True,
        group_operator="sum",
    )

    total_escaneos = fields.Integer(
        string="Total escaneos",
        compute="_compute_totales",
        store=True,
        group_operator="sum",
        help="Suma acumulada de escaneos en todos los registros del proyecto.",
    )

    etapa_dominante = fields.Char(
        string="Etapa más avanzada",
        compute="_compute_etapa_dominante",
        help="Etapa con mayor producción acumulada.",
    )

    # Restricciones Python

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

    @api.constrains("name")
    def _check_name(self):
        """El nombre del proyecto no puede estar vacío ni ser solo números."""
        for record in self:
            nombre = (record.name or "").strip()
            if not nombre:
                raise ValidationError(_("El nombre del proyecto no puede estar vacío."))
            if nombre.isdigit():
                raise ValidationError(
                    _(
                        "El nombre del proyecto no puede ser solo números: '%s'. "
                        "Usa un nombre descriptivo. Ej: 'Imprema 2026'.",
                        nombre,
                    )
                )

    @api.constrains("description")
    def _check_description_longitud(self):
        """La descripción no debe superar 5000 caracteres."""
        _MAX = 5000
        for record in self:
            if record.description and len(record.description) > _MAX:
                raise ValidationError(
                    _(
                        "La descripción no puede superar %d caracteres (actual: %d).",
                        _MAX,
                        len(record.description),
                    )
                )

    # Métodos computados

    @api.depends("fecha_inicio", "fecha_fin_estimada")
    def _compute_duracion_estimada(self):
        # El campo compute con store=True ya actualiza en el formulario
        # automáticamente. No se necesita @api.onchange adicional.
        for record in self:
            if record.fecha_inicio and record.fecha_fin_estimada:
                record.duracion_estimada = (
                    record.fecha_fin_estimada - record.fecha_inicio
                ).days
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
            miembros_activos = proyecto.miembro_ids.filtered(
                lambda miembro: not miembro.fecha_salida
            )
            proyecto.total_miembros = len(miembros_activos)
            proyecto.total_registros = len(proyecto.registro_ids)
            proyecto.total_escaneos = sum(
                registro.total_escaneos or 0 for registro in proyecto.registro_ids
            )

    @api.depends(
        "registro_ids", "registro_ids.produccion_principal", "registro_ids.etapa_nombre"
    )
    def _compute_etapa_dominante(self):
        for proyecto in self:
            if not proyecto.registro_ids:
                proyecto.etapa_dominante = _("Sin registros")
                continue

            # Agrupar producción por etapa
            totals = {}
            for reg in proyecto.registro_ids:
                nom = reg.etapa_nombre
                totals[nom] = totals.get(nom, 0) + (reg.produccion_principal or 0)

            if totals:
                top_etapa = max(totals, key=totals.get)
                proyecto.etapa_dominante = top_etapa
            else:
                proyecto.etapa_dominante = _("N/A")

    # Métodos de negocio

    def action_pausar(self):
        """Pone el proyecto en pausa (Standby)."""
        self.write({"state": "pausado"})

    def action_reactivar(self):
        """Reactiva un proyecto de cualquier estado a 'En curso'."""
        self.write({"state": "en_curso"})

    def action_finalizar(self):
        """Marca el proyecto como finalizado."""
        self.write({"state": "finalizado"})

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

    def action_ver_analisis_grafico(self):
        """Abre la vista de gráfico filtrada por este proyecto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Análisis de Producción — %s", self.name),
            "res_model": "digitalizacion.registro",
            "view_mode": "graph,pivot",
            "domain": [("proyecto_id", "=", self.id)],
            "context": {
                "default_proyecto_id": self.id,
                "search_default_proyecto_id": self.id,
                "group_by": ["fecha:day", "etapa_id"],
            },
            "target": "current",
        }

    def get_report_data(self):
        """Prepara los datos consolidados para el reporte PDF."""
        self.ensure_one()
        resumen_etapas = self.env["digitalizacion.registro"].get_resumen_por_proyecto(
            self.id
        )
        return {
            "proyecto": self,
            "miembros": self.miembro_ids,
            "resumen_etapas": resumen_etapas,
            "fecha_reporte": fields.Date.context_today(self),
        }

    def action_print_report(self):
        """Llama al reporte PDF desde el objeto."""
        return self.env.ref(
            "digitalizacion.action_report_proyecto_general"
        ).report_action(self)
