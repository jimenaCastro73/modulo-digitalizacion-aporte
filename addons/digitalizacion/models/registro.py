# -*- coding: utf-8 -*-
"""
registro.py — Modelo: digitalizacion.registro
Tabla T-06 · Registro diario de trabajo de digitalización

Granularidad:
    1 registro = 1 miembro + 1 etapa + cantidades acumuladas del día.
    El Líder agrega N registros por jornada, uno por cada combinación
    miembro+etapa trabajada ese día.

Campos de caja:
    referencia_cajas (Char) — texto libre. Acepta IDs separados por coma
    ("BF202, BF199, BF208") o descripciones ("7 cajas", "3 cajas aprox.").
    Fiel al proceso real donde las cajas no siempre tienen código asignado.

Orden de etapas (ciclo completo de una caja):
    1. Limpieza  2. Ordenado  3. Digitalizado  4. Editado  5. Indexado

Campos activos por etapa:
    Limpieza / Ordenado → referencia_cajas, no_expedientes, total_folios
    Digitalizado        → referencia_cajas, no_expedientes, total_folios,
                          total_escaneos, tipo_escaner_ids
    Editado             → expedientes_editados, folios_editados
    Indexado            → expedientes_indexados, folios_indexados

Relaciones:
    lider_id         → res.users                       (auditoría)
    miembro_id       → digitalizacion.miembro_proyecto (T-05)
    proyecto_id      → digitalizacion.proyecto         (T-03)
    etapa_id         → digitalizacion.etapa            (T-01)
    tipo_escaner_ids → digitalizacion.tipo_escaner     (T-02, Many2many)
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Registro(models.Model):
    _name = "digitalizacion.registro"
    _description = "Registro Diario de Trabajo de Digitalización"
    _order = "fecha desc, id desc"
    _rec_name = "display_name"

    # ── Auditoría y relaciones principales ───────────────────────────────────

    lider_id = fields.Many2one(
        comodel_name="res.users",
        string="Registrado por",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
        help="Usuario que realizó el registro. Auto-completado con el usuario en sesión.",
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
    )

    etapa_id = fields.Many2one(
        comodel_name="digitalizacion.etapa",
        string="Etapa",
        required=True,
        ondelete="restrict",
        index=True,
        help="Etapa del proceso. Determina qué campos son visibles.",
    )

    # ── Campos temporales ─────────────────────────────────────────────────────

    fecha = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.today,
        index=True,
    )

    hora = fields.Datetime(
        string="Hora de envío",
        default=fields.Datetime.now,
        readonly=True,
        help="Timestamp de cuando se guardó el formulario.",
    )

    # ── Campo común a todas las etapas ────────────────────────────────────────

    observacion = fields.Text(
        string="Observaciones",
        help="Incidencias, notas de la jornada, etc.",
    )

    # ── Campos etapa: Limpieza / Ordenado / Digitalizado ─────────────────────

    referencia_cajas = fields.Char(
        string="Referencia de cajas",
        help="Texto libre. Acepta IDs separados por coma (BF202, BF199) "
        "o descripciones ('7 cajas', '3 cajas aprox.'). "
        "Aplica a: Limpieza, Ordenado, Digitalizado.",
    )

    no_expedientes = fields.Integer(
        string="Cantidad de expedientes",
        help="Total de expedientes físicos procesados en la jornada. "
        "Aplica a: Limpieza, Ordenado.",
    )

    total_folios = fields.Integer(
        string="Cantidad de folios",
        help="Total de folios (hojas físicas) procesados. "
        "Aplica a: Limpieza, Ordenado, Digitalizado.",
    )

    # ── Campos etapa: Digitalizado ────────────────────────────────────────────

    total_escaneos = fields.Integer(
        string="Número de escaneos",
        help="Hojas digitales generadas. Aplica a: Digitalizado.",
    )

    tipo_escaner_ids = fields.Many2many(
        comodel_name="digitalizacion.tipo_escaner",
        string="Tipo(s) de escáner",
        help="Equipo(s) utilizados. Aplica a: Digitalizado.",
    )

    # ── Campos etapa: Editado ─────────────────────────────────────────────────

    expedientes_editados = fields.Integer(
        string="Expedientes editados",
        help="Expedientes que pasaron por edición digital. Aplica a: Editado.",
    )

    folios_editados = fields.Integer(
        string="Folios editados",
        help="Folios editados digitalmente. Aplica a: Editado.",
    )

    # ── Campos etapa: Indexado ────────────────────────────────────────────────

    expedientes_indexados = fields.Integer(
        string="Expedientes indexados",
        help="Expedientes con metadatos asignados. Aplica a: Indexado.",
    )

    folios_indexados = fields.Integer(
        string="Folios indexados",
        help="Folios digitales indexados. Aplica a: Indexado.",
    )

    # ── Campos computados y relacionados ──────────────────────────────────────

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
        help="Cantidad representativa según etapa.",
    )

    unidad_produccion = fields.Char(
        string="Unidad",
        compute="_compute_produccion_principal",
        store=True,
    )

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("miembro_id", "proyecto_id")
    def _check_miembro_pertenece_proyecto(self):
        for record in self:
            if record.miembro_id and record.proyecto_id:
                if record.miembro_id.proyecto_id.id != record.proyecto_id.id:
                    raise ValidationError(
                        _(
                            "El digitalizador '%s' no pertenece al proyecto '%s'.",
                            record.miembro_id.partner_id.name,
                            record.proyecto_id.name,
                        )
                    )

    @api.constrains("miembro_id")
    def _check_miembro_activo(self):
        for record in self:
            if record.miembro_id and record.miembro_id.fecha_salida:
                raise ValidationError(
                    _(
                        "'%s' tiene fecha de salida (%s). "
                        "No se pueden crear nuevos registros.",
                        record.miembro_id.partner_id.name,
                        record.miembro_id.fecha_salida,
                    )
                )

    @api.constrains("fecha")
    def _check_fecha_no_futura(self):
        hoy = fields.Date.today()
        for record in self:
            if record.fecha and record.fecha > hoy:
                raise ValidationError(
                    _(
                        "La fecha (%s) no puede ser futura.",
                        record.fecha,
                    )
                )

    @api.constrains(
        "no_expedientes",
        "total_folios",
        "total_escaneos",
        "expedientes_editados",
        "folios_editados",
        "expedientes_indexados",
        "folios_indexados",
    )
    def _check_valores_positivos(self):
        # Límite superior razonable: 999 999 unidades por jornada
        _MAX = 999_999
        campos = [
            ("no_expedientes",       _("Cantidad de expedientes")),
            ("total_folios",         _("Cantidad de folios")),
            ("total_escaneos",       _("Número de escaneos")),
            ("expedientes_editados", _("Expedientes editados")),
            ("folios_editados",      _("Folios editados")),
            ("expedientes_indexados",_("Expedientes indexados")),
            ("folios_indexados",     _("Folios indexados")),
        ]
        for record in self:
            for campo, etiqueta in campos:
                valor = getattr(record, campo)
                if valor < 0:
                    raise ValidationError(
                        _("%s no puede ser negativo (valor: %d).", etiqueta, valor)
                    )
                if valor > _MAX:
                    raise ValidationError(
                        _(
                            "%s supera el límite permitido de %d por jornada (valor: %d). "
                            "Verifica que el dato sea correcto.",
                            etiqueta, _MAX, valor,
                        )
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
        Valida que al menos un campo de producción esté informado según la etapa.
        Usa etapa_id.name en minúsculas para no hardcodear IDs.
        """
        for record in self:
            if not record.etapa_id:
                continue
            nombre = (record.etapa_id.name or "").lower()

            if "digitalizado" in nombre:
                if not (record.total_escaneos or record.total_folios):
                    raise ValidationError(
                        _(
                            "La etapa '%s' requiere 'Número de escaneos' o 'Cantidad de folios'.",
                            record.etapa_id.name,
                        )
                    )
            elif "editado" in nombre:
                if not (record.expedientes_editados or record.folios_editados):
                    raise ValidationError(
                        _(
                            "La etapa '%s' requiere 'Expedientes editados' o 'Folios editados'.",
                            record.etapa_id.name,
                        )
                    )
            elif "indexado" in nombre:
                if not (record.expedientes_indexados or record.folios_indexados):
                    raise ValidationError(
                        _(
                            "La etapa '%s' requiere 'Expedientes indexados' o 'Folios indexados'.",
                            record.etapa_id.name,
                        )
                    )
            elif "limpieza" in nombre or "ordenado" in nombre:
                if not (record.no_expedientes or record.total_folios):
                    raise ValidationError(
                        _(
                            "La etapa '%s' requiere 'Expedientes' o 'Folios'.",
                            record.etapa_id.name,
                        )
                    )

    @api.constrains("referencia_cajas")
    def _check_referencia_cajas(self):
        """
        referencia_cajas es texto libre, pero si se ingresa debe:
          - No ser solo espacios en blanco.
          - Contener al menos una letra o un dígito (no solo símbolos).
        """
        for record in self:
            ref = record.referencia_cajas
            if ref is False or ref is None:
                continue
            ref_strip = ref.strip()
            if not ref_strip:
                raise ValidationError(
                    _("'Referencia de cajas' no puede contener solo espacios en blanco.")
                )
            # Debe tener al menos un caracter alfanumérico
            if not re.search(r'[\w\d]', ref_strip):
                raise ValidationError(
                    _(
                        "'Referencia de cajas' debe contener al menos una letra o número "
                        "(valor ingresado: '%s').",
                        ref_strip,
                    )
                )

    @api.constrains("observacion")
    def _check_observacion_longitud(self):
        """La observación no debe superar los 2000 caracteres."""
        _MAX_CHARS = 2000
        for record in self:
            if record.observacion and len(record.observacion) > _MAX_CHARS:
                raise ValidationError(
                    _(
                        "Las observaciones no pueden superar %d caracteres "
                        "(actual: %d).",
                        _MAX_CHARS,
                        len(record.observacion),
                    )
                )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("lider_id", "miembro_id", "etapa_id", "fecha")
    def _compute_display_name(self):
        for record in self:
            miembro = record.miembro_id.partner_id.name or "?"
            etapa = record.etapa_id.name or "?"
            fecha = str(record.fecha) if record.fecha else "?"
            record.display_name = f"{miembro} · {etapa} · {fecha}"

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
        for record in self:
            nombre = (record.etapa_id.name or "").lower()
            if "digitalizado" in nombre:
                record.produccion_principal = record.total_escaneos or 0
                record.unidad_produccion = "escaneos"
            elif "editado" in nombre:
                record.produccion_principal = record.expedientes_editados or 0
                record.unidad_produccion = "exp. editados"
            elif "indexado" in nombre:
                record.produccion_principal = record.expedientes_indexados or 0
                record.unidad_produccion = "exp. indexados"
            elif "limpieza" in nombre or "ordenado" in nombre:
                record.produccion_principal = record.no_expedientes or 0
                record.unidad_produccion = "expedientes"
            else:
                record.produccion_principal = record.total_folios or 0
                record.unidad_produccion = "folios"

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange("etapa_id")
    def _onchange_etapa(self):
        """Limpia campos que no corresponden a la etapa seleccionada."""
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
        # Limpiar campos de caja solo si la etapa no los usa
        if not any(e in nombre for e in ("limpieza", "ordenado", "digitalizado")):
            self.referencia_cajas = False
            self.no_expedientes = 0

    @api.onchange("proyecto_id")
    def _onchange_proyecto_limpiar_miembro(self):
        """Al cambiar el proyecto limpia miembro_id y retorna domain actualizado."""
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

    # ── Overrides CRUD ────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Fuerza lider_id y hora con valores del servidor."""
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
                "Intento de modificar lider_id en registro(s) %s. Ignorado.",
                self.ids,
            )
        return super().write(vals)

    # ── Métodos de negocio ────────────────────────────────────────────────────

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
            "name": _("Registro duplicado"),
            "res_model": "digitalizacion.registro",
            "res_id": nuevo.id,
            "view_mode": "form",
            "target": "current",
        }

    # ── Métodos de consulta para portal y reportes ────────────────────────────

    @api.model
    def get_kpis_lider(self, lider_id, domain_extra=None):
        """
        KPIs del dashboard para el líder.
        Usa _read_group para que la suma ocurra en PostgreSQL.

        Retorna:
            {
                "escaneos":        int,
                "folios_fisicos":  int,
                "exp_indexados":   int,
                "total_registros": int,
            }
        """
        domain = [("lider_id", "=", lider_id)] + (domain_extra or [])
        data = self.sudo()._read_group(
            domain=domain,
            groupby=[],
            aggregates=[
                "total_escaneos:sum",
                "total_folios:sum",
                "expedientes_indexados:sum",
                "__count",
            ],
        )
        if data:
            escaneos, folios, indexados, total = data[0]
        else:
            escaneos, folios, indexados, total = 0, 0, 0, 0
        return {
            "escaneos": escaneos or 0,
            "folios_fisicos": folios or 0,
            "exp_indexados": indexados or 0,
            "total_registros": total,
        }

    @api.model
    def get_resumen_por_etapa(self, proyecto_id):
        """
        Resumen de producción agrupado por etapa para un proyecto.
        Usado en el dashboard del backend.

        Retorna:
            [{"etapa": "Digitalizado", "total": 1840, "unidad": "escaneos"}, ...]
        """
        registros = self.sudo().search([("proyecto_id", "=", proyecto_id)])
        resumen = {}
        for record in registros:
            etapa = record.etapa_id.name or "Sin etapa"
            if etapa not in resumen:
                resumen[etapa] = {
                    "etapa": etapa,
                    "total": 0,
                    "unidad": record.unidad_produccion,
                }
            resumen[etapa]["total"] += record.produccion_principal or 0
        return sorted(resumen.values(), key=lambda x: x["etapa"])

    @api.model
    def get_participacion_equipo(self, proyecto_id):
        """
        Participación de cada miembro por etapa para un proyecto.
        Usado en la vista de miembros del portal: gráfico de barras apiladas
        + tabla heatmap. Una sola query agrupada, sin N+1.

        Retorna:
        {
            "etapas": ["Limpieza", "Ordenado", ...],   # en orden de sequence
            "miembros": [
                {
                    "nombre": "María López",
                    "total": 20,
                    "por_etapa": {"Limpieza": 4, "Digitalizado": 7, ...},
                    "segmentos": [                      # para barras apiladas
                        {"etapa": "Limpieza", "count": 4, "pct": 20},
                        {"etapa": "Digitalizado", "count": 7, "pct": 35},
                        ...
                    ],
                },
                ...
            ],
        }
        """
        # Una sola query agrupada por miembro y etapa
        datos = self.sudo()._read_group(
            domain=[("proyecto_id", "=", proyecto_id)],
            groupby=["miembro_id", "etapa_id"],
            aggregates=["__count"],
        )

        # Etapas en orden de sequence (para columnas y leyenda)
        etapas_orden = (
            self.env["digitalizacion.etapa"]
            .sudo()
            .search([("active", "=", True)], order="sequence asc")
            .mapped("name")
        )

        # Construir mapa { miembro_id: { etapa_nombre: count } }
        mapa = {}
        for miembro, etapa, count in datos:
            mid = miembro.id
            if mid not in mapa:
                mapa[mid] = {
                    "nombre": miembro.partner_id.name or miembro.display_name,
                    "por_etapa": {},
                    "total": 0,
                }
            etapa_nombre = etapa.name or "Sin etapa"
            mapa[mid]["por_etapa"][etapa_nombre] = count
            mapa[mid]["total"] += count

        # Ordenar por total descendente
        miembros_ordenados = sorted(
            mapa.values(), key=lambda m: m["total"], reverse=True
        )

        # Agregar segmentos para las barras apiladas CSS en QWeb
        for m in miembros_ordenados:
            total = m["total"] or 1
            m["segmentos"] = [
                {
                    "etapa": etapa,
                    "count": m["por_etapa"].get(etapa, 0),
                    "pct": round((m["por_etapa"].get(etapa, 0) / total) * 100),
                }
                for etapa in etapas_orden
                if m["por_etapa"].get(etapa, 0) > 0
            ]

        return {
            "etapas": etapas_orden,
            "miembros": miembros_ordenados,
        }
