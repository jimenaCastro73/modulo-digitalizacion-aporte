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
  - Al asignar un Líder a un proyecto (T-04), el sistema crea automáticamente
    su entrada aquí (ver asignacion.py · _crear_miembro_para_lider).
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

    es_lider = fields.Boolean(
        string="Es líder",
        compute="_compute_es_lider",
        search="_search_es_lider",
        store=False,
        help="True si este contacto es el partner del líder asignado al proyecto.",
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

    def write(self, vals):
        """
        Override para normalizar: si se escribe fecha_salida,
        desactivar automáticamente el miembro.
        """
        res = super().write(vals)
        if "fecha_salida" in vals and vals["fecha_salida"]:
            # Desactivar los que aún estén activos
            activos = self.filtered(lambda r: r.active)
            if activos:
                super(MiembroProyecto, activos).write({"active": False})
        return res

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("partner_id", "proyecto_id")
    def _compute_display_name(self):
        for rec in self:
            nombre = rec.partner_id.name or "Sin nombre"
            proyecto = rec.proyecto_id.name or "Sin proyecto"
            rec.display_name = f"{nombre} ({proyecto})"

    @api.depends("proyecto_id", "partner_id")
    def _compute_es_lider(self):
        """
        Determina si este miembro es el partner del líder asignado al proyecto.
        Útil para mostrar indicadores visuales en la vista del backend.
        Optimizado: carga todas las asignaciones activas en un solo query.
        """
        if not self.ids:
            return
        Asignacion = self.env["digitalizacion.asignacion"]
        proyecto_ids = self.mapped("proyecto_id").ids
        asignaciones = Asignacion.search(
            [
                ("proyecto_id", "in", proyecto_ids),
                ("active", "=", True),
            ]
        )
        # Mapa: proyecto_id → partner_id del líder
        lider_partner_map = {}
        for asig in asignaciones:
            lider_partner_map.setdefault(asig.proyecto_id.id, set()).add(
                asig.lider_id.partner_id.id
            )
        for rec in self:
            partners = lider_partner_map.get(rec.proyecto_id.id, set())
            rec.es_lider = rec.partner_id.id in partners

    def _search_es_lider(self, operator, value):
        Asignacion = self.env["digitalizacion.asignacion"]
        asignaciones = Asignacion.search([("active", "=", True)])
        miembros_ids = []
        for asig in asignaciones:
            if asig.proyecto_id and asig.lider_id.partner_id:
                m = self.search(
                    [
                        ("proyecto_id", "=", asig.proyecto_id.id),
                        ("partner_id", "=", asig.lider_id.partner_id.id),
                    ]
                )
                miembros_ids.extend(m.ids)

        if (operator == "=" and value) or (operator == "!=" and not value):
            return [("id", "in", miembros_ids)]
        return [("id", "not in", miembros_ids)]

    @api.depends("proyecto_id", "partner_id")
    def _compute_total_registros(self):
        """Cuenta registros por miembro. Optimizado con _read_group."""
        if not self.ids:
            return
        Registro = self.env["digitalizacion.registro"]
        datos = Registro._read_group(
            domain=[("miembro_id", "in", self.ids)],
            groupby=["miembro_id"],
            aggregates=["__count"],
        )
        conteos = {miembro.id: count for miembro, count in datos}
        for rec in self:
            rec.total_registros = conteos.get(rec.id, 0)

    def _search_total_registros(self, operator, value):
        if operator == "=" and value == 0:
            # Miembros que NO tienen registros
            miembros_con = (
                self.env["digitalizacion.registro"].search([]).mapped("miembro_id.id")
            )
            return [("id", "not in", miembros_con)]
        elif (operator == ">" and value == 0) or (operator == "!=" and value == 0):
            # Miembros que SÍ tienen registros
            miembros_con = (
                self.env["digitalizacion.registro"].search([]).mapped("miembro_id.id")
            )
            return [("id", "in", miembros_con)]
        raise NotImplementedError(
            "Búsqueda no soportada para total_registros con este operador y valor."
        )

    # name_get() eliminado: Odoo 17 usa _compute_display_name (definido arriba)

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
            rec.write(
                {
                    "fecha_salida": hoy,
                    "active": False,
                }
            )

    def action_reintegrar(self):
        """
        Cancela la salida del miembro: limpia fecha_salida y reactiva.
        Útil para corregir registros erróneos.
        """
        for rec in self:
            rec.write(
                {
                    "fecha_salida": False,
                    "active": True,
                }
            )

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
        desde el portal web. Implementa la lógica nota 3.7:

          1. Si partner_id informado → usar partner existente.
          2. Si solo nombre → buscar en res.partner (=ilike).
             a. Encontrado → usar.
             b. No encontrado → crear res.partner nuevo.
          3. Validar UNIQUE antes de crear miembro_proyecto.
          4. Retornar dict con {id, name} del nuevo miembro.

        Lanza ValidationError si hay duplicado.
        """
        Partner = self.env["res.partner"].sudo()

        # ── Resolver partner ─────────────────────────────────────────────────
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

        # ── Verificar duplicado ──────────────────────────────────────────────
        existente = self.with_context(active_test=False).search(
            [
                ("proyecto_id", "=", proyecto_id),
                ("partner_id", "=", partner.id),
            ],
            limit=1,
        )

        if existente:
            if existente.active:
                raise ValidationError(
                    f"'{partner.name}' ya es miembro activo de este proyecto."
                )
            else:
                # Reactivar miembro archivado
                existente.write({"active": True, "fecha_salida": False})
                _logger.info(
                    "Miembro_proyecto reactivado: '%s' en proyecto ID %d.",
                    partner.name,
                    proyecto_id,
                )
                return {"id": existente.id, "name": partner.name}

        # ── Crear nuevo miembro_proyecto ─────────────────────────────────────
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
