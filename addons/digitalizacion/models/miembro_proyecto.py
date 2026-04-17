# -*- coding: utf-8 -*-
"""
miembro_proyecto.py — Modelo: digitalizacion.miembro_proyecto
Tabla T-05 · Integrantes del equipo de digitalización por proyecto

Puente entre el catálogo global de contactos (res.partner) y los proyectos.
SOLO el admin puede gestionar miembros desde el backend.

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
  - Al reintentar crear un miembro existente (con fecha_salida), se reactiva automáticamente
  - Al marcar "Es líder", se asigna automáticamente el grupo 'Líder' al usuario portal
  - Al desmarcar "Es líder" (si no es líder en otros proyectos), se remueve el grupo
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

    # Campos

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

    es_lider = fields.Boolean(
        string="Es líder",
        default=False,
        help="Marca este miembro como líder del proyecto. "
        "Solo puede haber un líder activo por proyecto. "
        "Al activar, crea o reactiva la asignación en T-04. "
        "Al desactivar, desactiva la asignación correspondiente.",
    )

    # Campo computado para saber si está activo (sin fecha_salida)
    is_active = fields.Boolean(
        string="Activo",
        compute="_compute_is_active",
        store=True,
        help="Activo si no tiene fecha_salida",
    )

    # Campos relacionados almacenados

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

    # Campos computados

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

    # Restricciones Python

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
                        ("fecha_salida", "=", False),
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

    # Métodos computados

    @api.depends("fecha_salida")
    def _compute_is_active(self):
        for record in self:
            record.is_active = not bool(record.fecha_salida)

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

    # Overrides CRUD

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea miembros. Si ya existe un registro (con fecha_salida) para el mismo
        proyecto/partner, lo reactiva en lugar de crear uno nuevo.
        Si es_lider=True, sincroniza con asignación.
        """
        registros_a_crear = []

        for vals in vals_list:
            # Buscar si ya existe un registro para este proyecto y partner (incluso con fecha_salida)
            existente = self.search(
                [
                    ("proyecto_id", "=", vals.get("proyecto_id")),
                    ("partner_id", "=", vals.get("partner_id")),
                ],
                limit=1,
            )

            if existente:
                # Si existe, lo reactivamos limpiando fecha_salida
                valores_reactivacion = {
                    "fecha_salida": False,
                    "fecha_integracion": vals.get(
                        "fecha_integracion", fields.Date.today()
                    ),
                    "es_lider": vals.get("es_lider", False),
                }
                existente.write(valores_reactivacion)

                # Si se está marcando como líder, sincronizar
                if existente.es_lider:
                    existente._sincronizar_liderazgo(True)

                _logger.info(
                    "Miembro reactivado: %s en proyecto %s",
                    existente.partner_id.name,
                    existente.proyecto_id.name,
                )
            else:
                # No existe, crear nuevo
                registros_a_crear.append(vals)

        if registros_a_crear:
            records = super().create(registros_a_crear)
            for record in records:
                if record.es_lider:
                    record._sincronizar_liderazgo(True)
            return records

        return self.env["digitalizacion.miembro_proyecto"]

    def write(self, vals):
        """
        Sincroniza es_lider con digitalizacion.asignacion (T-04).
        Si se informa fecha_salida, limpia liderazgo si corresponde.
        """
        # Guardar estado actual antes de escribir
        old_es_lider = {r.id: r.es_lider for r in self}
        old_fecha_salida = {r.id: r.fecha_salida for r in self}

        res = super().write(vals)

        # Verificar si se limpió fecha_salida (reactivación)
        for record in self:
            if (
                "fecha_salida" in vals
                and not vals.get("fecha_salida")
                and old_fecha_salida.get(record.id)
                and record.es_lider
            ):
                record._sincronizar_liderazgo(True)

        # Sincronizar cambios de liderazgo
        if "es_lider" in vals:
            for record in self:
                new_es_lider = vals.get("es_lider")
                if new_es_lider != old_es_lider.get(record.id):
                    record._sincronizar_liderazgo(new_es_lider)

        # Si se estableció fecha_salida, desactivar liderazgo
        if vals.get("fecha_salida"):
            lideres = self.filtered(lambda r: r.es_lider)
            if lideres:
                for record in lideres:
                    record._sincronizar_liderazgo(False)
                    # Limpiar es_lider también
                    super(DigitalizacionMiembroProyecto, lideres).write(
                        {"es_lider": False}
                    )

        return res

    # Sincronización con digitalizacion.asignacion

    def _sincronizar_liderazgo(self, activar):
        """
        Sincroniza es_lider con digitalizacion.asignacion (T-04).

        activar=True:
          1. Verificar que el partner tenga usuario portal activo.
          2. Asignar grupo líder automáticamente si no lo tiene.
          3. Desmarcar otros líderes del mismo proyecto.
          4. Crear o reactivar la asignación.

        activar=False:
          1. Verificar si es líder en otros proyectos.
          2. Si no es líder en ningún proyecto, quitar grupo líder.
          3. Desactivar la asignación.
        """
        self.ensure_one()
        if activar:
            self._activar_liderazgo()
        else:
            self._desactivar_liderazgo()

    def _activar_liderazgo(self):
        """Valida usuario portal, asigna grupo líder y crea/reactiva asignación."""
        self.ensure_one()
        Asignacion = self.env["digitalizacion.asignacion"].sudo()
        GrupoLider = self.env.ref("digitalizacion.group_digitalizacion_lider")

        # Buscar usuario portal vinculado al partner
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
                    "Primero debe crearle un usuario portal (Contactos → Otorgar acceso a portal) "
                    "y luego marcarlo como líder.",
                    self.partner_id.name,
                )
            )

        # Asignar grupo de líder automáticamente si no lo tiene
        if GrupoLider not in usuario.groups_id:
            usuario.write({"groups_id": [(4, GrupoLider.id)]})
            _logger.info(
                "Grupo 'Líder' asignado automáticamente al usuario '%s' (login: %s)",
                usuario.name,
                usuario.login,
            )

        # Desmarcar otros líderes del mismo proyecto (activos)
        otros_lideres = self.search(
            [
                ("proyecto_id", "=", self.proyecto_id.id),
                ("es_lider", "=", True),
                ("id", "!=", self.id),
                ("fecha_salida", "=", False),
            ]
        )
        for otro in otros_lideres:
            otro._desactivar_asignacion_sin_remover_grupo()
        if otros_lideres:
            super(DigitalizacionMiembroProyecto, otros_lideres).write(
                {"es_lider": False}
            )
            _logger.info(
                "Otros líderes desmarcados en proyecto '%s': %s",
                self.proyecto_id.name,
                [otro.partner_id.name for otro in otros_lideres],
            )

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

    def _desactivar_liderazgo(self):
        """
        Desactiva liderazgo:
        1. Verifica si es líder en otros proyectos activos.
        2. Si no es líder en ningún otro proyecto, quita el grupo líder.
        3. Desactiva la asignación en T-04.
        """
        self.ensure_one()
        GrupoLider = self.env.ref("digitalizacion.group_digitalizacion_lider")

        # Buscar usuario portal vinculado al partner
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

        if usuario:
            # Verificar si sigue siendo líder en algún otro proyecto activo
            es_lider_en_otro = self.search(
                [
                    ("partner_id", "=", self.partner_id.id),
                    ("es_lider", "=", True),
                    ("fecha_salida", "=", False),
                    ("id", "!=", self.id),
                ],
                limit=1,
            )

            if not es_lider_en_otro and GrupoLider in usuario.groups_id:
                usuario.write({"groups_id": [(3, GrupoLider.id)]})
                _logger.info(
                    "Grupo 'Líder' removido del usuario '%s' (ya no es líder en ningún proyecto)",
                    usuario.name,
                )
        else:
            _logger.warning(
                "No se encontró usuario portal para '%s' al desactivar liderazgo",
                self.partner_id.name,
            )

        # Desactivar asignación
        self._desactivar_asignacion_sin_remover_grupo()

    def _desactivar_asignacion_sin_remover_grupo(self):
        """Desactiva la asignación activa sin tocar el grupo del usuario."""
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

    # Métodos de negocio (solo admin)

    def action_registrar_salida(self):
        """Registra la salida del miembro: asigna fecha_salida=hoy."""
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
            record.write({"fecha_salida": hoy})

    def action_reintegrar(self):
        """Cancela la salida: limpia fecha_salida."""
        for record in self:
            record.write({"fecha_salida": False})

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
