# -*- coding: utf-8 -*-
"""
registro.py — Modelo: digitalizacion.registro
Tabla T-06 · Registro diario de trabajo de digitalización

CAMBIOS DRY/KISS respecto a la versión original:
  - validar_fila_api()→ absorbe _validar_fila() que vivía en portal.py. El modelo sabe validar sus propios datos.
  - _compute_produccion_principal → usa ETAPAS_CONFIG (constantes.py) en vez de if/elif por etapa.
  - get_resumen_etapas() → absorbido desde el helper en portal.py.
  - El controlador ahora llama a estos métodos y solo maneja HTTP.

SIMPLIFICACIÓN (alineación con Excel original):
  - Eliminados: expedientes_editados, folios_editados.
    En el Excel, la etapa Editado usa la misma columna "No expedientes" que
    Limpieza/Ordenado. Los campos específicos eran redundantes y no tenían
    respaldo en los datos reales del cliente.
  - Indexado conserva expedientes_indexados y folios_indexados porque en el
    Excel son columnas independientes (no se usa usa "No expedientes" para indexar).

El resto de campos y métodos (KPIs, participación equipo, etc.) no cambian
porque ya estaban bien encapsulados en el modelo.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools.constantes import ETAPA_DEFAULT_CONFIG, ETAPAS_CONFIG
from ..tools.utils import (
    sanitizar_entero,
    sanitizar_referencia_cajas,
    sanitizar_texto,
    validar_id_positivo,
)

_logger = logging.getLogger(__name__)


class DigitalizacionRegistro(models.Model):
    _name = "digitalizacion.registro"
    _description = "Registro Diario de Trabajo de Digitalización"
    _order = "fecha desc, id desc"
    _rec_name = "display_name"

    # Auditoría y relaciones principales

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

    etapa_nombre = fields.Char(
        related="etapa_id.name",
        string="Nombre de la etapa",
        store=True,
    )

    # Métrica Principal (Consolidada)

    produccion_principal = fields.Integer(
        string="Producción principal",
        compute="_compute_produccion_principal",
        store=True,
        group_operator="sum",
        help="Cantidad representativa según etapa.",
    )

    unidad_produccion = fields.Char(
        string="Unidad",
        compute="_compute_produccion_principal",
        store=True,
    )

    # Campos temporales

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

    # Campo común a todas las etapas

    observacion = fields.Text(
        string="Observaciones",
        help="Incidencias, notas de la jornada, etc.",
    )

    referencia_cajas = fields.Char(
        string="Referencia de cajas",
        help="Texto libre. Acepta IDs separados por coma (BF202, BF199) "
        "o descripciones ('7 cajas', '3 cajas aprox.'). "
        "Aplica a: Limpieza, Ordenado, Digitalizado.",
    )

    # ── Campos de producción ──────────────────────────────────────────────────
    # Compartidos por Limpieza, Ordenado, Digitalizado y Editado:
    no_expedientes = fields.Integer(
        string="Cantidad de expedientes", group_operator="sum"
    )
    total_folios = fields.Integer(string="Cantidad de folios", group_operator="sum")

    # Exclusivo de Digitalizado:
    total_escaneos = fields.Integer(string="Número de escaneos", group_operator="sum")
    tipo_escaner_ids = fields.Many2many(
        comodel_name="digitalizacion.tipo_escaner", string="Tipo(s) de escáner"
    )

    # Exclusivos de Indexado (columnas independientes en el Excel):
    expedientes_indexados = fields.Integer(
        string="Expedientes indexados", group_operator="sum"
    )
    folios_indexados = fields.Integer(string="Folios indexados", group_operator="sum")

    # Campos computados / relacionados

    display_name = fields.Char(compute="_compute_display_name", store=False)
    miembro_nombre = fields.Char(
        string="Nombre del Digitalizador",
        related="miembro_id.partner_id.name",
        store=True,
        readonly=True,
        index=True,
    )
    proyecto_nombre = fields.Char(
        string="Nombre del Proyecto",
        related="proyecto_id.name",
        store=True,
        readonly=True,
    )
    etapa_nombre = fields.Char(
        string="Nombre de la Etapa",
        related="etapa_id.name",
        store=True,
        readonly=True,
        index=True,
    )
    lider_nombre = fields.Char(
        string="Nombre del Líder", related="lider_id.name", store=True, readonly=True
    )

    # Restricciones Python

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
                        "'%s' tiene fecha de salida (%s). No se pueden crear nuevos registros.",
                        record.miembro_id.partner_id.name,
                        record.miembro_id.fecha_salida,
                    )
                )

    # Métodos computados

    @api.depends(
        "etapa_id",
        "no_expedientes",
        "total_folios",
        "total_escaneos",
        "folios_indexados",
    )
    def _compute_produccion_principal(self):
        """
        Determina produccion_principal y unidad_produccion según la etapa.

        PRINCIPIO DRY: usa ETAPAS_CONFIG del módulo constantes.py en vez
        de un bloque if/elif por cada etapa. Agregar una nueva etapa solo
        requiere añadir una entrada al diccionario.
        """
        for record in self:
            nombre_etapa = record.etapa_id.name if record.etapa_id else ""
            config = ETAPAS_CONFIG.get(nombre_etapa, ETAPA_DEFAULT_CONFIG)
            campo = config["campo_principal"]
            record.produccion_principal = getattr(record, campo, 0) or 0
            record.unidad_produccion = config["unidad"]

    @api.depends("fecha", "miembro_id", "etapa_id")
    def _compute_display_name(self):
        for record in self:
            fecha = record.fecha.strftime("%d/%m/%Y") if record.fecha else "—"
            miembro = record.miembro_nombre or "Sin digitalizador"
            etapa = record.etapa_nombre or "Sin etapa"
            record.display_name = f"{fecha} · {miembro} · {etapa}"

    # API de validación (movida desde portal.py)

    @api.model
    def validar_fila_api(self, fila, idx):
        """
        Valida y normaliza una fila del payload JSON del portal.

        PRINCIPIO DRY/KISS:
          Antes, _validar_fila() vivía en portal.py mezclada con lógica HTTP.
          El controlador no debería saber cómo validar sus propios datos —
          eso es responsabilidad del modelo.

        `idx` es el índice 1-based para mensajes de error descriptivos.
        Retorna un dict limpio listo para ORM, o lanza ValidationError.
        """
        prefijo = _("Fila %d", idx)

        miembro_id = validar_id_positivo(fila.get("miembro_id"), "miembro_id", prefijo)
        etapa_id = validar_id_positivo(fila.get("etapa_id"), "etapa_id", prefijo)

        # tipo_escaner_ids: lista de enteros (IDs válidos únicamente)
        escaner_raw = fila.get("tipo_escaner_ids", [])
        tipo_escaner_ids = []
        if isinstance(escaner_raw, list):
            for eid in escaner_raw:
                try:
                    tipo_escaner_ids.append(int(eid))
                except (TypeError, ValueError):
                    pass  # IDs inválidos se ignoran silenciosamente

        # Campos numéricos de producción
        no_expedientes = sanitizar_entero(fila.get("no_expedientes"), _("Expedientes"))
        total_folios = sanitizar_entero(fila.get("total_folios"), _("Folios totales"))
        total_escaneos = sanitizar_entero(fila.get("total_escaneos"), _("Escaneos"))
        expedientes_indexados = sanitizar_entero(
            fila.get("expedientes_indexados"), _("Exp. indexados")
        )
        folios_indexados = sanitizar_entero(
            fila.get("folios_indexados"), _("Folios indexados")
        )

        # Campos de texto
        referencia_cajas = sanitizar_referencia_cajas(
            fila.get("referencia_cajas"), prefijo
        )
        observacion = sanitizar_texto(fila.get("observacion"), _("Observación"))

        return {
            "miembro_id": miembro_id,
            "etapa_id": etapa_id,
            "tipo_escaner_ids": [(6, 0, tipo_escaner_ids)],
            "no_expedientes": no_expedientes,
            "total_folios": total_folios,
            "total_escaneos": total_escaneos,
            "expedientes_indexados": expedientes_indexados,
            "folios_indexados": folios_indexados,
            "referencia_cajas": referencia_cajas,
            "observacion": observacion,
        }

    # API de KPIs y reportes

    @api.model
    def get_resumen_etapas(self, domain):
        """
        Resumen de producción por etapa para el dashboard del portal.
        Retorna: lista de dicts [{"nombre": str, "cantidad": int}]
        """
        if not domain:
            domain = []

        registros = self.sudo().search(domain)

        if not registros:
            return [{"nombre": "Sin registros", "cantidad": 0}]

        conteo = {}
        for reg in registros:
            etapa_nombre = reg.etapa_nombre or "Sin etapa"
            conteo[etapa_nombre] = conteo.get(etapa_nombre, 0) + 1

        result = []
        for etapa_nombre, cantidad in conteo.items():
            result.append({"nombre": etapa_nombre, "cantidad": cantidad})

        result.sort(key=lambda x: x["cantidad"], reverse=True)

        return result

    @api.model
    def get_resumen_por_etapa(self, proyecto_id):
        """
        Resumen de producción por etapa para reportes del proyecto.
        Compatible with get_report_data() in proyecto.py.
        """
        domain = [("proyecto_id", "=", proyecto_id)]
        return self.get_resumen_etapas(domain)

    @api.model
    def get_kpis_lider(self, lider_id, domain_extra=None):
        """KPIs del líder adaptados a las llaves que espera el template del portal."""
        domain = [("lider_id", "=", lider_id)]
        if domain_extra:
            domain += domain_extra

        registros = self.sudo().search(domain)

        return {
            "total_registros": len(registros),
            "escaneos": sum(registros.mapped("total_escaneos") or [0]),
            "folios_fisicos": sum(registros.mapped("total_folios") or [0]),
            "exp_indexados": sum(registros.mapped("expedientes_indexados") or [0]),
        }

    @api.model
    def get_resumen_por_proyecto(self, proyecto_id):
        """Resumen de producción agrupada por etapa para un proyecto."""
        registros = self.sudo().search([("proyecto_id", "=", proyecto_id)])
        resumen = {}
        for r in registros:
            nombre_etapa = r.etapa_id.name or "Sin etapa"
            if nombre_etapa not in resumen:
                resumen[nombre_etapa] = {
                    "etapa": nombre_etapa,
                    "total": 0,
                    "unidad": r.unidad_produccion,
                }
            resumen[nombre_etapa]["total"] += r.produccion_principal or 0
        return sorted(resumen.values(), key=lambda x: x["etapa"])

    @api.model
    def get_participacion_equipo(self, proyecto_id):
        """
        Participación de cada miembro por etapa para un proyecto.
        Sin cambios — ya era eficiente con _read_group en la versión original.
        """
        datos = self.sudo()._read_group(
            domain=[("proyecto_id", "=", proyecto_id)],
            groupby=["miembro_id", "etapa_id"],
            aggregates=["__count"],
        )
        etapas_en_orden = (
            self.env["digitalizacion.etapa"]
            .sudo()
            .search([("active", "=", True)], order="sequence asc")
            .mapped("name")
        )
        participacion = {}
        for miembro, etapa, cantidad in datos:
            key = miembro.id
            if key not in participacion:
                participacion[key] = {
                    "nombre": miembro.partner_id.name or miembro.display_name,
                    "por_etapa": {},
                    "total": 0,
                }
            nombre_etapa = etapa.name or "Sin etapa"
            participacion[key]["por_etapa"][nombre_etapa] = cantidad
            participacion[key]["total"] += cantidad

        miembros_ordenados = sorted(
            participacion.values(), key=lambda d: d["total"], reverse=True
        )
        for datos_miembro in miembros_ordenados:
            total_p = datos_miembro["total"] or 1
            datos_miembro["segmentos"] = [
                {
                    "etapa": etapa,
                    "count": datos_miembro["por_etapa"].get(etapa, 0),
                    "pct": round(
                        (datos_miembro["por_etapa"].get(etapa, 0) / total_p) * 100
                    ),
                }
                for etapa in etapas_en_orden
                if datos_miembro["por_etapa"].get(etapa, 0) > 0
            ]
        return {"etapas": etapas_en_orden, "miembros": miembros_ordenados}
