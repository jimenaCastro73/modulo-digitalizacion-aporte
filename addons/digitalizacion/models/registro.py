# -*- coding: utf-8 -*-
"""
registro.py — Modelo: digitalizacion.registro
Tabla T-06 · Registro diario de trabajo de digitalización

Granularidad:
    1 registro = 1 miembro + 1 etapa + cantidades acumuladas del día.
    El Líder agrega N registros por jornada, uno por cada combinación
    miembro+etapa trabajada. Un mismo miembro puede tener múltiples registros
    en el mismo día si trabajó en varias etapas.

Estrategia de tabla plana con campos opcionales por etapa:
    Los campos que no corresponden a la etapa activa quedan en NULL.
    La visibilidad dinámica se controla en la vista QWeb del portal (WF-03)
    y en la vista de formulario del backend mediante attrs/invisible.

Relaciones:
    lider_id         → res.users                        (auditoría, auto env.user)
    miembro_id       → digitalizacion.miembro_proyecto  (T-05, digitalizador)
    proyecto_id      → digitalizacion.proyecto          (T-03)
    etapa_id         → digitalizacion.etapa             (T-01)
    tipo_escaner_ids → digitalizacion.tipo_escaner      (T-02, Many2many)
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Registro(models.Model):
    _name = "digitalizacion.registro"
    _description = "Registro Diario de Trabajo de Digitalización"
    _order = "fecha desc, id desc"
    _rec_name = "display_name"

    # =========================================================================
    # CAMPOS DE AUDITORÍA Y RELACIONES PRINCIPALES
    # =========================================================================

    lider_id = fields.Many2one(
        comodel_name="res.users",
        string="Registrado por (Líder)",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
        help="Usuario Odoo que realizó el registro. Auto-completado con el usuario en sesión.",
    )

    miembro_id = fields.Many2one(
        comodel_name="digitalizacion.miembro_proyecto",
        string="Digitalizador",
        required=True,
        ondelete="restrict",
        index=True,
        help="Integrante del equipo al que pertenece el trabajo registrado.",
    )

    proyecto_id = fields.Many2one(
        comodel_name="digitalizacion.proyecto",
        string="Proyecto",
        required=True,
        ondelete="restrict",
        index=True,
        help="Proyecto al que pertenece el registro.",
    )

    etapa_id = fields.Many2one(
        comodel_name="digitalizacion.etapa",
        string="Etapa",
        required=True,
        ondelete="restrict",
        index=True,
        help="Etapa del proceso. Determina qué campos de detalle son visibles.",
    )

    # =========================================================================
    # CAMPOS TEMPORALES
    # =========================================================================

    fecha = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.today,
        index=True,
        help="Fecha de la jornada registrada. Default: hoy.",
    )

    hora = fields.Datetime(
        string="Hora de envío",
        default=fields.Datetime.now,
        readonly=True,
        help="Timestamp de cuando se guardó el formulario. Capturado automáticamente.",
    )

    # =========================================================================
    # CAMPO COMÚN A TODAS LAS ETAPAS
    # =========================================================================

    observacion = fields.Text(
        string="Observaciones",
        help="Campo libre de texto. Incidencias, notas de la jornada, etc.",
    )

    # =========================================================================
    # CAMPOS ETAPA: LIMPIEZA / ORDENADO
    # =========================================================================

    no_caja = fields.Char(
        string="Nombre / ID de caja",
        help="ETAPAS: Limpieza, Ordenado. Identificador de la caja procesada. "
        "Acepta texto libre (ej: '504A, 504B, 504C').",
    )

    cantidad_cajas = fields.Integer(
        string="Cantidad de cajas",
        help="ETAPAS: Limpieza, Ordenado. Número de cajas físicas procesadas.",
    )

    no_expedientes = fields.Integer(
        string="Cantidad de expedientes",
        help="ETAPAS: Limpieza, Ordenado. Número de expedientes físicos procesados.",
    )

    total_folios = fields.Integer(
        string="Cantidad de folios",
        help="ETAPAS: Limpieza, Ordenado, Digitalizado. Número de folios (hojas físicas) procesados.",
    )

    # =========================================================================
    # CAMPOS ETAPA: DIGITALIZADO
    # =========================================================================

    total_escaneos = fields.Integer(
        string="Número de escaneos",
        help="ETAPA: Digitalizado. Número de hojas digitales generadas (scans).",
    )

    tipo_escaner_ids = fields.Many2many(
        comodel_name="digitalizacion.tipo_escaner",
        string="Tipo(s) de escáner",
        help="ETAPA: Digitalizado. Equipo(s) utilizados en la sesión. Many2many (nota 3.4).",
    )

    # =========================================================================
    # CAMPOS ETAPA: EDITADO
    # =========================================================================

    expedientes_editados = fields.Integer(
        string="Expedientes editados",
        help="ETAPA: Editado. Número de expedientes que pasaron por edición digital.",
    )

    folios_editados = fields.Integer(
        string="Folios editados",
        help="ETAPA: Editado. Número de folios editados digitalmente.",
    )

    # =========================================================================
    # CAMPOS ETAPA: INDEXADO
    # =========================================================================

    expedientes_indexados = fields.Integer(
        string="Expedientes indexados",
        help="ETAPA: Indexado. Número de expedientes a los que se asignaron metadatos.",
    )

    folios_indexados = fields.Integer(
        string="Folios indexados",
        help="ETAPA: Indexado. Número de folios digitales indexados.",
    )

    # =========================================================================
    # CAMPOS COMPUTADOS Y RELACIONADOS
    # =========================================================================

    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=False,
    )

    miembro_nombre = fields.Char(
        string="Nombre del digitalizador",
        related="miembro_id.partner_id.name",
        store=True,
        readonly=True,
        index=True,
    )

    proyecto_nombre = fields.Char(
        string="Nombre del proyecto",
        related="proyecto_id.name",
        store=True,
        readonly=True,
    )

    etapa_nombre = fields.Char(
        string="Nombre de la etapa",
        related="etapa_id.name",
        store=True,
        readonly=True,
        index=True,
    )

    lider_nombre = fields.Char(
        string="Nombre del líder",
        related="lider_id.name",
        store=True,
        readonly=True,
    )

    produccion_principal = fields.Integer(
        string="Producción principal",
        compute="_compute_produccion_principal",
        store=True,
        help="Cantidad representativa de la etapa: escaneos, expedientes o folios según etapa.",
    )

    unidad_produccion = fields.Char(
        string="Unidad",
        compute="_compute_produccion_principal",
        store=True,
        help="Etiqueta de la unidad: 'escaneos', 'expedientes', 'folios edit.', etc.",
    )

    # =========================================================================
    # RESTRICCIONES PYTHON
    # =========================================================================

    @api.constrains("miembro_id", "proyecto_id")
    def _check_miembro_pertenece_proyecto(self):
        """Verifica que el miembro_id pertenezca al proyecto_id del registro."""
        for rec in self:
            if rec.miembro_id and rec.proyecto_id:
                if rec.miembro_id.proyecto_id.id != rec.proyecto_id.id:
                    raise ValidationError(
                        f"El digitalizador '{rec.miembro_id.partner_id.name}' "
                        f"no pertenece al proyecto '{rec.proyecto_id.name}'."
                    )

    @api.constrains("miembro_id")
    def _check_miembro_activo(self):
        """Verifica que el miembro no tenga fecha_salida al momento de registrar."""
        for rec in self:
            if rec.miembro_id and rec.miembro_id.fecha_salida:
                raise ValidationError(
                    f"'{rec.miembro_id.partner_id.name}' tiene fecha de salida "
                    f"({rec.miembro_id.fecha_salida}). No se pueden crear nuevos registros."
                )

    @api.constrains("fecha")
    def _check_fecha_no_futura(self):
        """El registro no puede ser de una fecha futura."""
        hoy = fields.Date.today()
        for rec in self:
            if rec.fecha and rec.fecha > hoy:
                raise ValidationError(
                    f"La fecha ({rec.fecha}) no puede ser futura. "
                    f"El registro debe corresponder a una jornada ya trabajada."
                )

    @api.constrains(
        "etapa_id",
        "total_escaneos",
        "expedientes_editados",
        "folios_editados",
        "expedientes_indexados",
        "folios_indexados",
        "no_expedientes",
        "total_folios",
    )
    def _check_campos_minimos_por_etapa(self):
        """
        Valida que al menos un campo numérico de producción esté informado
        según la etapa. Evita registros vacíos sin datos de producción.
        La validación se basa en etapa_id.name (sin hardcodear IDs).
        """
        for rec in self:
            if not rec.etapa_id:
                continue

            nombre = (rec.etapa_id.name or "").lower()

            if "digitalizado" in nombre:
                if not (rec.total_escaneos or rec.total_folios):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere "
                        f"'Número de escaneos' o 'Cantidad de folios'."
                    )
            elif "editado" in nombre:
                if not (rec.expedientes_editados or rec.folios_editados):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere "
                        f"'Expedientes editados' o 'Folios editados'."
                    )
            elif "indexado" in nombre:
                if not (rec.expedientes_indexados or rec.folios_indexados):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere "
                        f"'Expedientes indexados' o 'Folios indexados'."
                    )
            elif "limpieza" in nombre or "ordenado" in nombre:
                if not (rec.no_expedientes or rec.total_folios or rec.cantidad_cajas):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere "
                        f"'Expedientes', 'Folios' o 'Cajas'."
                    )

    # =========================================================================
    # MÉTODOS COMPUTADOS
    # =========================================================================

    @api.depends("lider_id", "miembro_id", "etapa_id", "fecha")
    def _compute_display_name(self):
        for rec in self:
            miembro = rec.miembro_id.partner_id.name or "?"
            etapa = rec.etapa_id.name or "?"
            fecha = str(rec.fecha) if rec.fecha else "?"
            rec.display_name = f"{miembro} · {etapa} · {fecha}"

    @api.depends(
        "etapa_id",
        "etapa_id.name",
        "total_escaneos",
        "no_expedientes",
        "expedientes_editados",
        "expedientes_indexados",
        "folios_editados",
        "folios_indexados",
        "total_folios",
    )
    def _compute_produccion_principal(self):
        """
        Determina la cantidad y unidad representativa según la etapa.
        store=True para filtros y reportes eficientes.
        """
        for rec in self:
            nombre = (rec.etapa_id.name or "").lower()

            if "digitalizado" in nombre:
                rec.produccion_principal = rec.total_escaneos or 0
                rec.unidad_produccion = "escaneos"
            elif "editado" in nombre:
                rec.produccion_principal = rec.expedientes_editados or 0
                rec.unidad_produccion = "exp. editados"
            elif "indexado" in nombre:
                rec.produccion_principal = rec.expedientes_indexados or 0
                rec.unidad_produccion = "exp. indexados"
            elif "limpieza" in nombre or "ordenado" in nombre:
                rec.produccion_principal = rec.no_expedientes or 0
                rec.unidad_produccion = "expedientes"
            else:
                rec.produccion_principal = rec.total_folios or 0
                rec.unidad_produccion = "folios"

    # =========================================================================
    # ONCHANGE
    # =========================================================================

    @api.onchange("etapa_id")
    def _onchange_etapa(self):
        """
        Limpia los campos que no corresponden a la etapa seleccionada.
        Evita valores residuales de una etapa anterior.
        """
        nombre = (self.etapa_id.name or "").lower() if self.etapa_id else ""

        if "digitalizado" not in nombre:
            self.total_escaneos = 0
            self.tipo_escaner_ids = [(5, 0, 0)]

        if "editado" not in nombre:
            self.expedientes_editados = 0
            self.folios_editados = 0

        if "indexado" not in nombre:
            self.expedientes_indexados = 0
            self.folios_indexados = 0

        if "limpieza" not in nombre and "ordenado" not in nombre:
            self.cantidad_cajas = 0
            self.no_expedientes = 0

    @api.onchange("proyecto_id")
    def _onchange_proyecto_limpiar_miembro(self):
        """
        Al cambiar el proyecto limpia miembro_id y retorna el domain actualizado.
        """
        self.miembro_id = False
        if self.proyecto_id:
            return {
                "domain": {
                    "miembro_id": [
                        ("proyecto_id", "=", self.proyecto_id.id),
                        ("active", "=", True),
                        ("fecha_salida", "=", False),
                    ]
                }
            }

    # =========================================================================
    # OVERRIDE CREATE / WRITE
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """
        Asegura que lider_id y hora queden completados con el usuario
        y timestamp actuales, sin importar lo que envíe el cliente.
        """
        lider_id = self.env.user.id
        ahora = fields.Datetime.now()
        for vals in vals_list:
            vals["lider_id"] = lider_id
            if not vals.get("hora"):
                vals["hora"] = ahora
        return super().create(vals_list)

    def write(self, vals):
        """Impide que lider_id sea modificado después de la creación."""
        if "lider_id" in vals:
            vals.pop("lider_id")
            _logger.warning(
                "Intento de modificar lider_id en registro(s) %s. Ignorado.", self.ids
            )
        return super().write(vals)

    # =========================================================================
    # MÉTODOS DE NEGOCIO
    # =========================================================================

    def action_duplicar_para_hoy(self):
        """Duplica el registro cambiando la fecha a hoy."""
        self.ensure_one()
        nuevo = self.copy(
            default={
                "fecha": fields.Date.today(),
                "hora": fields.Datetime.now(),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Registro duplicado",
            "res_model": "digitalizacion.registro",
            "res_id": nuevo.id,
            "view_mode": "form",
        }

    # =========================================================================
    # MÉTODOS DE CONSULTA PARA EL PORTAL Y REPORTES
    # =========================================================================

    @api.model
    def get_kpis_lider(self, lider_id: int, domain_extra: list = None) -> dict:
        """
        Calcula los KPIs del dashboard para el líder indicado.
        Usado desde el controller del portal y desde el dashboard del backend.

        Retorna:
            {
                "escaneos":        int,
                "folios_fisicos":  int,
                "exp_indexados":   int,
                "total_registros": int,
            }
        """
        domain = [("lider_id", "=", lider_id)]
        if domain_extra:
            domain += domain_extra
        registros = self.sudo().search(domain)
        return {
            "escaneos": sum(r.total_escaneos or 0 for r in registros),
            "folios_fisicos": sum(r.total_folios or 0 for r in registros),
            "exp_indexados": sum(r.expedientes_indexados or 0 for r in registros),
            "total_registros": len(registros),
        }

    @api.model
    def get_resumen_por_etapa(self, proyecto_id: int) -> list:
        """
        Resumen de producción agrupado por etapa para un proyecto.
        Usado en el dashboard del backend (Administrador).

        Retorna:
            [{"etapa": "Digitalizado", "total": 1840, "unidad": "escaneos"}, ...]
        """
        registros = self.sudo().search([("proyecto_id", "=", proyecto_id)])
        resumen = {}
        for rec in registros:
            etapa = rec.etapa_id.name or "Sin etapa"
            if etapa not in resumen:
                resumen[etapa] = {
                    "etapa": etapa,
                    "total": 0,
                    "unidad": rec.unidad_produccion,
                }
            resumen[etapa]["total"] += rec.produccion_principal or 0
        return sorted(resumen.values(), key=lambda x: x["etapa"])
