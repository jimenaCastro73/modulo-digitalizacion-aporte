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
  - Al marcar es_lider = True en un miembro, el sistema crea/reactiva
    automáticamente su registro en digitalizacion.asignacion (T-04),
    que es el que habilita el acceso al portal y controla las reglas de
    seguridad. Solo puede haber un líder activo por proyecto.
  - Al desmarcar es_lider, se desactiva la asignación correspondiente.
  - Si fecha_salida está informada, el miembro NO aparece en el selector del
    formulario de registro (filtro en domain de registro.miembro_id).
  - Un mismo contacto puede ser miembro de múltiples proyectos con distintas
    fechas de integración.

Referenciado por:
  - digitalizacion.registro (miembro_id)  → T-06
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MiembroProyecto(models.Model):
    _name = "digitalizacion.miembro_proyecto"
    _description = "Miembro del Equipo de Digitalización"
    _order = "proyecto_id asc, partner_id asc"
    _rec_name = "display_name"

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
        help="Integrante del equipo. Referencia a res.partner. "
        "Si no existe, se crea desde el portal antes de vincular.",
    )

    fecha_integracion = fields.Date(
        string="Fecha de integración",
        default=fields.Date.today,
        help="Fecha en que el integrante se sumó al proyecto. "
        "Permite incorporaciones tardías.",
    )

    fecha_salida = fields.Date(
        string="Fecha de salida",
        help="Opcional. Fecha en que el integrante dejó el proyecto. "
        "Si está informada, el miembro NO aparece en el selector "
        "del formulario de registro.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Soft delete. False = miembro inactivo, no aparece en el "
        "selector del formulario de registro.",
    )

    es_lider = fields.Boolean(
        string="Es líder",
        default=False,
        help="Marca este miembro como líder del proyecto. "
        "Solo puede haber un líder activo por proyecto. "
        "Al activar, crea o reactiva la asignación en T-04, "
        "habilitando el acceso al portal. Al desactivar, "
        "desactiva la asignación correspondiente.",
    )

    # ── Campos relacionados (lectura rápida sin JOIN explícito) ───────────────

    partner_name = fields.Char(
        string="Nombre del miembro",
        related="partner_id.name",
        store=True,  # almacenado para búsquedas y ordenamiento eficiente
        readonly=True,
    )

    proyecto_name = fields.Char(
        string="Nombre del proyecto",
        related="proyecto_id.name",
        store=True,
        readonly=True,
    )

    # ── Campo computado ───────────────────────────────────────────────────────

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

    # ── Restricciones SQL ─────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "unique_miembro_proyecto",
            "UNIQUE(proyecto_id, partner_id)",
            "Este contacto ya es miembro del proyecto seleccionado.",
        ),
    ]

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("fecha_integracion", "fecha_salida")
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_salida and rec.fecha_integracion:
                if rec.fecha_salida < rec.fecha_integracion:
                    raise ValidationError(
                        f"La fecha de salida de '{rec.partner_id.name}' "
                        f"no puede ser anterior a su fecha de integración."
                    )

    @api.constrains("es_lider", "proyecto_id")
    def _check_lider_unico(self):
        """Garantiza que solo haya un líder activo por proyecto."""
        for rec in self:
            if rec.es_lider and rec.proyecto_id:
                otros = self.search(
                    [
                        ("proyecto_id", "=", rec.proyecto_id.id),
                        ("es_lider", "=", True),
                        ("id", "!=", rec.id),
                        ("active", "=", True),
                    ]
                )
                if otros:
                    raise ValidationError(
                        f"El proyecto '{rec.proyecto_id.name}' ya tiene un líder activo: "
                        f"'{otros[0].partner_id.name}'. Desactívalo primero."
                    )

    # ── Overrides write / create ──────────────────────────────────────────────

    def write(self, vals):
        """
        Sincroniza es_lider con digitalizacion.asignacion (T-04).
        Normaliza fecha_salida: si se informa, desactiva el miembro.
        """
        res = super().write(vals)

        # Sincronizar liderazgo si cambió es_lider
        if "es_lider" in vals:
            for rec in self:
                rec._sincronizar_liderazgo(rec.es_lider)

        # Si se escribe fecha_salida, desactivar miembro y limpiar liderazgo
        if "fecha_salida" in vals and vals["fecha_salida"]:
            activos = self.filtered(lambda r: r.active)
            if activos:
                super(MiembroProyecto, activos).write({"active": False})
            # Si era líder, quitar liderazgo y desactivar asignación
            lideres = self.filtered(lambda r: r.es_lider)
            if lideres:
                for rec in lideres:
                    rec._sincronizar_liderazgo(False)
                super(MiembroProyecto, lideres).write({"es_lider": False})

        return res

    # ── Métodos de sincronización con asignacion ──────────────────────────────

    def _sincronizar_liderazgo(self, activar: bool):
        """
        Sincroniza el campo es_lider con digitalizacion.asignacion (T-04).

        Lógica:
          activar=True:
            1. Verificar que el partner tenga un usuario Odoo portal activo.
            2. Desmarcar otros miembros líderes del mismo proyecto (write directo
               a super() para evitar recursión) y desactivar sus asignaciones.
            3. Crear o reactivar la asignación para este miembro.

          activar=False:
            1. Buscar la asignación activa del usuario correspondiente.
            2. Desactivarla.
        """
        self.ensure_one()
        Asignacion = self.env["digitalizacion.asignacion"].sudo()

        if activar:
            # 1. Buscar usuario portal del partner
            usuario = (
                self.env["res.users"]
                .sudo()
                .search(
                    [
                        ("partner_id", "=", self.partner_id.id),
                        ("share", "=", True),  # usuario portal
                        ("active", "=", True),
                    ],
                    limit=1,
                )
            )

            if not usuario:
                raise ValidationError(
                    f"'{self.partner_id.name}' no tiene un usuario portal de Odoo. "
                    f"Crea el usuario antes de marcarlo como líder."
                )

            # 2. Desmarcar otros líderes del mismo proyecto y desactivar sus asignaciones
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
                # Usar super() para evitar recursión en write
                super(MiembroProyecto, otros_lideres).write({"es_lider": False})

            # 3. Crear o reactivar asignación para este miembro
            asig_existente = Asignacion.with_context(active_test=False).search(
                [
                    ("proyecto_id", "=", self.proyecto_id.id),
                    ("lider_id", "=", usuario.id),
                ],
                limit=1,
            )

            if asig_existente:
                if not asig_existente.active:
                    asig_existente.write({"active": True})
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
                        "fecha_asignacion": self.fecha_integracion
                        or fields.Date.today(),
                    }
                )
                _logger.info(
                    "Asignación creada: líder '%s' en proyecto '%s'.",
                    self.partner_id.name,
                    self.proyecto_id.name,
                )

        else:
            # Desactivar asignación si existe
            self._desactivar_asignacion()

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
        for rec in self:
            nombre = rec.partner_id.name or "Sin nombre"
            proyecto = rec.proyecto_id.name or "Sin proyecto"
            rec.display_name = f"{nombre} ({proyecto})"

    @api.depends("proyecto_id", "partner_id")
    def _compute_total_registros(self):
        """Cuenta registros por miembro. Optimizado con _read_group."""
        conteos = {}
        reales = self.filtered(lambda r: r.id)
        if reales:
            Registro = self.env["digitalizacion.registro"]
            datos = Registro._read_group(
                domain=[("miembro_id", "in", reales.ids)],
                groupby=["miembro_id"],
                aggregates=["__count"],
            )
            conteos = {miembro.id: count for miembro, count in datos}

        for rec in self:
            rec.total_registros = conteos.get(rec.id, 0)

    def _search_total_registros(self, operator, value):
        if operator == "=" and value == 0:
            miembros_con = (
                self.env["digitalizacion.registro"].search([]).mapped("miembro_id.id")
            )
            return [("id", "not in", miembros_con)]
        elif (operator == ">" and value == 0) or (operator == "!=" and value == 0):
            miembros_con = (
                self.env["digitalizacion.registro"].search([]).mapped("miembro_id.id")
            )
            return [("id", "in", miembros_con)]
        raise NotImplementedError(
            "Búsqueda no soportada para total_registros con este operador y valor."
        )

    # ── Métodos de negocio ────────────────────────────────────────────────────

    def action_registrar_salida(self):
        """
        Registra la salida del miembro: asigna fecha_salida = hoy y
        desactiva el registro (soft delete).
        """
        hoy = fields.Date.today()
        for rec in self:
            if rec.fecha_salida:
                raise ValidationError(
                    f"'{rec.partner_id.name}' ya tiene fecha de salida registrada: "
                    f"{rec.fecha_salida}."
                )
            rec.write({"fecha_salida": hoy, "active": False})

    def action_reintegrar(self):
        """
        Cancela la salida del miembro: limpia fecha_salida y reactiva.
        Útil para corregir registros erróneos.
        """
        for rec in self:
            rec.write({"fecha_salida": False, "active": True})

    def action_ver_registros(self):
        """Abre los registros de trabajo de este miembro en el proyecto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Registros — {self.partner_id.name}",
            "res_model": "digitalizacion.registro",
            "view_mode": "list,form",
            "domain": [
                ("miembro_id", "=", self.id),
                ("proyecto_id", "=", self.proyecto_id.id),
            ],
            "context": {
                "default_miembro_id": self.id,
                "default_proyecto_id": self.proyecto_id.id,
            },
        }

    # ── Método de clase: creación desde el portal (API pública) ──────────────

    @api.model
    def crear_desde_portal(
        self,
        proyecto_id: int,
        nombre: str,
        partner_id: int = None,
        fecha_integracion=None,
    ):
        """
        Método de alto nivel llamado desde el controlador al agregar un miembro
        desde el portal web. Implementa la lógica nota 3.7.
        """
        Partner = self.env["res.partner"].sudo()

        if partner_id:
            partner = Partner.browse(partner_id)
            if not partner.exists():
                raise ValidationError(f"El contacto ID {partner_id} no existe.")
        else:
            nombre_limpio = (nombre or "").strip()
            if not nombre_limpio:
                raise ValidationError("El nombre del miembro no puede estar vacío.")
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
                    f"'{partner.name}' ya es miembro activo de este proyecto."
                )
            else:
                existente.write({"active": True, "fecha_salida": False})
                _logger.info(
                    "Miembro_proyecto reactivado: '%s' en proyecto ID %d.",
                    partner.name,
                    proyecto_id,
                )
                return {"id": existente.id, "name": partner.name}

        fecha = fecha_integracion or fields.Date.today()
        nuevo = self.sudo().create(
            {
                "proyecto_id": proyecto_id,
                "partner_id": partner.id,
                "fecha_integracion": fecha,
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
