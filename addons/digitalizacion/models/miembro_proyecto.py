# -*- coding: utf-8 -*-
"""
miembro_proyecto.py — Modelo: digitalizacion.miembro_proyecto
Tabla T-05 · Integrantes del equipo de digitalización por proyecto

Puente entre el catálogo global de contactos (res.partner) y los proyectos.
Permite al Líder gestionar su equipo desde el portal: consultar miembros,
agregar nuevos y registrar incorporaciones tardías.

Reglas de negocio clave:
  - UNIQUE(proyecto_id, partner_id): un contacto no puede aparecer dos veces
    en el mismo proyecto.
  - es_lider = True crea/reactiva automáticamente el registro en
    digitalizacion.asignacion (T-04), habilitando el acceso al portal.
    Solo puede haber un líder activo por proyecto.
  - Al desmarcar es_lider, se desactiva la asignación correspondiente.
  - Si fecha_salida está informada, el miembro NO aparece en el selector del
    formulario de registro.
  - Un mismo contacto puede ser miembro de múltiples proyectos.

Referenciado por:
  - digitalizacion.registro (miembro_id)  → T-06
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DigitalizacionMiembroProyecto(models.Model):
    _name = "digitalizacion.miembro_proyecto"
    _description = "Miembro del Equipo de Digitalización"
    _order = "proyecto_id asc, partner_id asc"
    _rec_name = "display_name"

    _sql_constraints = [
        (
            "unique_miembro_proyecto",
            "UNIQUE(proyecto_id, partner_id)",
            "Este contacto ya es miembro del proyecto seleccionado.",
        ),
    ]

    # ── Campos ────────────────────────────────────────────────────────────────

    proyecto_id = fields.Many2one(
        comodel_name="digitalizacion.proyecto",
        string="Proyecto",
        required=True,
        ondelete="restrict",
        index=True,
        help="Proyecto al que pertenece el integrante.",
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contacto",
        required=True,
        ondelete="restrict",
        index=True,
        help="Integrante del equipo. Referencia a res.partner.",
    )

    fecha_integracion = fields.Date(
        string="Fecha de integración",
        default=fields.Date.today,
        help="Fecha en que el integrante se sumó al proyecto.",
    )

    fecha_salida = fields.Date(
        string="Fecha de salida",
        help="Opcional. Si está informada, el miembro no aparece en el selector del formulario de registro.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete. False = miembro inactivo.",
    )

    es_lider = fields.Boolean(
        string="Es líder",
        default=False,
        help="Marca este miembro como líder del proyecto. "
        "Solo puede haber un líder activo por proyecto. "
        "Al activar, crea o reactiva la asignación en T-04. "
        "Al desactivar, desactiva la asignación correspondiente.",
    )

    # ── Campos relacionados almacenados ───────────────────────────────────────

    partner_name = fields.Char(
        string="Nombre del miembro",
        related="partner_id.name",
        store=True,
        readonly=True,
    )

    proyecto_name = fields.Char(
        string="Nombre del proyecto",
        related="proyecto_id.name",
        store=True,
        readonly=True,
    )

    # ── Campos computados ─────────────────────────────────────────────────────

    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=False,
    )

    total_registros = fields.Integer(
        string="Registros de trabajo",
        compute="_compute_total_registros",
        search="_search_total_registros",
        store=False,
        help="Cantidad de registros de trabajo asociados a este miembro en el proyecto.",
    )

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("fecha_integracion", "fecha_salida")
    def _check_fechas(self):
        for record in self:
            if record.fecha_salida and record.fecha_integracion:
                if record.fecha_salida < record.fecha_integracion:
                    raise ValidationError(
                        _(
                            "La fecha de salida de '%s' no puede ser anterior "
                            "a su fecha de integración.",
                            record.partner_id.name,
                        )
                    )

    @api.constrains("es_lider", "proyecto_id")
    def _check_lider_unico(self):
        """Garantiza que solo haya un líder activo por proyecto."""
        for record in self:
            if record.es_lider and record.proyecto_id:
                otros = self.search(
                    [
                        ("proyecto_id", "=", record.proyecto_id.id),
                        ("es_lider", "=", True),
                        ("id", "!=", record.id),
                        ("active", "=", True),
                    ]
                )
                if otros:
                    raise ValidationError(
                        _(
                            "El proyecto '%s' ya tiene un líder activo: '%s'. "
                            "Desactívalo primero.",
                            record.proyecto_id.name,
                            otros[0].partner_id.name,
                        )
                    )

    # ── Overrides CRUD ────────────────────────────────────────────────────────

    def write(self, vals):
        """
        Sincroniza es_lider con digitalizacion.asignacion (T-04).
        Si se informa fecha_salida, desactiva el miembro y limpia liderazgo.
        """
        res = super().write(vals)

        if "es_lider" in vals:
            for record in self:
                record._sincronizar_liderazgo(record.es_lider)

        if vals.get("fecha_salida"):
            activos = self.filtered(lambda r: r.active)
            if activos:
                super(DigitalizacionMiembroProyecto, activos).write({"active": False})
            lideres = self.filtered(lambda r: r.es_lider)
            if lideres:
                for record in lideres:
                    record._sincronizar_liderazgo(False)
                super(DigitalizacionMiembroProyecto, lideres).write({"es_lider": False})

        return res

    # ── Sincronización con digitalizacion.asignacion ──────────────────────────

    def _sincronizar_liderazgo(self, activar):
        """
        Sincroniza es_lider con digitalizacion.asignacion (T-04).

        activar=True:
          1. Verificar que el partner tenga usuario portal activo.
          2. Desmarcar otros líderes del mismo proyecto.
          3. Crear o reactivar la asignación.

        activar=False:
          1. Buscar y desactivar la asignación activa.
        """
        self.ensure_one()
        if activar:
            self._activar_liderazgo()
        else:
            self._desactivar_asignacion()

    def _activar_liderazgo(self):
        """Valida usuario portal y crea/reactiva la asignación en T-04."""
        self.ensure_one()
        Asignacion = self.env["digitalizacion.asignacion"].sudo()

        usuario = (
            self.env["res.users"]
            .sudo()
            .search(
                [
                    ("partner_id", "=", self.partner_id.id),
                    ("share", "=", True),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

        if not usuario:
            raise ValidationError(
                _(
                    "'%s' no tiene un usuario portal de Odoo. "
                    "Crea el usuario antes de marcarlo como líder.",
                    self.partner_id.name,
                )
            )

        # Desmarcar otros líderes del mismo proyecto
        otros_lideres = self.search(
            [
                ("proyecto_id", "=", self.proyecto_id.id),
                ("es_lider", "=", True),
                ("id", "!=", self.id),
                ("active", "=", True),
            ]
        )
        for otro in otros_lideres:
            otro._desactivar_asignacion()
        if otros_lideres:
            super(DigitalizacionMiembroProyecto, otros_lideres).write({"es_lider": False})

        # Crear o reactivar asignación
        asig = Asignacion.with_context(active_test=False).search(
            [
                ("proyecto_id", "=", self.proyecto_id.id),
                ("lider_id", "=", usuario.id),
            ],
            limit=1,
        )

        if asig:
            if not asig.active:
                asig.write({"active": True})
                _logger.info(
                    "Asignación reactivada: líder '%s' en proyecto '%s'.",
                    self.partner_id.name,
                    self.proyecto_id.name,
                )
        else:
            Asignacion.create(
                {
                    "proyecto_id": self.proyecto_id.id,
                    "lider_id": usuario.id,
                    "fecha_asignacion": self.fecha_integracion or fields.Date.today(),
                }
            )
            _logger.info(
                "Asignación creada: líder '%s' en proyecto '%s'.",
                self.partner_id.name,
                self.proyecto_id.name,
            )

    def _desactivar_asignacion(self):
        """Busca y desactiva la asignación activa de este miembro en su proyecto."""
        self.ensure_one()
        usuario = (
            self.env["res.users"]
            .sudo()
            .search(
                [
                    ("partner_id", "=", self.partner_id.id),
                    ("share", "=", True),
                ],
                limit=1,
            )
        )
        if not usuario:
            return
        asig = (
            self.env["digitalizacion.asignacion"]
            .sudo()
            .search(
                [
                    ("proyecto_id", "=", self.proyecto_id.id),
                    ("lider_id", "=", usuario.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )
        if asig:
            asig.write({"active": False})
            _logger.info(
                "Asignación desactivada: líder '%s' en proyecto '%s'.",
                self.partner_id.name,
                self.proyecto_id.name,
            )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("partner_id", "proyecto_id")
    def _compute_display_name(self):
        for record in self:
            nombre = record.partner_id.name or "Sin nombre"
            proyecto = record.proyecto_id.name or "Sin proyecto"
            record.display_name = f"{nombre} ({proyecto})"

    @api.depends("proyecto_id", "partner_id")
    def _compute_total_registros(self):
        """Cuenta registros por miembro. Optimizado con _read_group."""
        conteos = {}
        reales = self.filtered(lambda r: r.id)
        if reales:
            datos = self.env["digitalizacion.registro"]._read_group(
                domain=[("miembro_id", "in", reales.ids)],
                groupby=["miembro_id"],
                aggregates=["__count"],
            )
            conteos = {miembro.id: count for miembro, count in datos}
        for record in self:
            record.total_registros = conteos.get(record.id, 0)

    def _search_total_registros(self, operator, value):
        # Optimizado: _read_group en vez de search([]).mapped()
        datos = self.env["digitalizacion.registro"]._read_group(
            [], ["miembro_id"], ["__count"]
        )
        miembros_con = [miembro.id for miembro, _ in datos if miembro]

        if operator == "=" and value == 0:
            return [("id", "not in", miembros_con)]
        if (operator == ">" and value == 0) or (operator == "!=" and value == 0):
            return [("id", "in", miembros_con)]
        raise NotImplementedError(
            _("Búsqueda no soportada para total_registros con este operador.")
        )

    # ── Métodos de negocio ────────────────────────────────────────────────────

    def action_registrar_salida(self):
        """Registra la salida del miembro: asigna fecha_salida=hoy y desactiva."""
        hoy = fields.Date.today()
        for record in self:
            if record.fecha_salida:
                raise ValidationError(
                    _(
                        "'%s' ya tiene fecha de salida registrada: %s.",
                        record.partner_id.name,
                        record.fecha_salida,
                    )
                )
            record.write({"fecha_salida": hoy, "active": False})

    def action_reintegrar(self):
        """Cancela la salida: limpia fecha_salida y reactiva."""
        for record in self:
            record.write({"fecha_salida": False, "active": True})

    def action_ver_registros(self):
        """Abre los registros de trabajo de este miembro en el proyecto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registros — %s", self.partner_id.name),
            "res_model": "digitalizacion.registro",
            "view_mode": "tree,form",
            "domain": [
                ("miembro_id", "=", self.id),
                ("proyecto_id", "=", self.proyecto_id.id),
            ],
            "context": {
                "default_miembro_id": self.id,
                "default_proyecto_id": self.proyecto_id.id,
            },
            "target": "current",
        }

    # ── Método de clase: creación desde el portal ─────────────────────────────

    @api.model
    def crear_desde_portal(
        self, proyecto_id, nombre, partner_id=None, fecha_integracion=None
    ):
        """
        Método de alto nivel llamado desde el controlador al agregar un miembro
        desde el portal web. Implementa la lógica nota 3.7.
        """
        Partner = self.env["res.partner"].sudo()

        if partner_id:
            partner = Partner.browse(partner_id)
            if not partner.exists():
                raise ValidationError(_("El contacto ID %s no existe.", partner_id))
        else:
            nombre_limpio = (nombre or "").strip()
            if not nombre_limpio:
                raise ValidationError(_("El nombre del miembro no puede estar vacío."))
            partner = Partner.search(
                [("name", "=ilike", nombre_limpio), ("active", "=", True)],
                limit=1,
            )
            if not partner:
                partner = Partner.create({"name": nombre_limpio})
                _logger.info(
                    "Nuevo res.partner creado desde portal: '%s' (ID %d)",
                    nombre_limpio,
                    partner.id,
                )

        existente = self.with_context(active_test=False).search(
            [("proyecto_id", "=", proyecto_id), ("partner_id", "=", partner.id)],
            limit=1,
        )

        if existente:
            if existente.active:
                raise ValidationError(
                    _("'%s' ya es miembro activo de este proyecto.", partner.name)
                )
            existente.write({"active": True, "fecha_salida": False})
            _logger.info(
                "Miembro_proyecto reactivado: '%s' en proyecto ID %d.",
                partner.name,
                proyecto_id,
            )
            return {"id": existente.id, "name": partner.name}

        nuevo = self.sudo().create(
            {
                "proyecto_id": proyecto_id,
                "partner_id": partner.id,
                "fecha_integracion": fecha_integracion or fields.Date.today(),
                "active": True,
            }
        )
        _logger.info(
            "Miembro_proyecto creado desde portal: '%s' (ID %d) en proyecto ID %d.",
            partner.name,
            nuevo.id,
            proyecto_id,
        )
        return {"id": nuevo.id, "name": partner.name}
