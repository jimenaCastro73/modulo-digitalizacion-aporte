# -*- coding: utf-8 -*-
"""
portal.py — Controller HTTP del portal del Líder
Módulo de Gestión de Digitalización · Odoo 17

Rutas GET (vistas):
    /digitalizacion/v1/dashboard                    → dashboard
    /digitalizacion/v1/proyectos/<id>/form          → formulario_registro
    /digitalizacion/v1/proyectos/<id>               → proyecto_detalle
    /digitalizacion/v1/proyectos/<id>/miembros      → proyecto_miembros

Rutas POST (JSON API):
    /digitalizacion/api/v1/proyectos/<id>/registros → api_guardar_registros

Permisos:
    Todas las rutas requieren auth='user' y grupo digitalizacion_lider.
    El líder solo accede a proyectos donde tiene asignación activa.
    La vista de miembros es solo lectura — el admin gestiona el equipo
    desde el backoffice.
"""

import json
import logging
from datetime import date, timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

# Máximo de notificaciones en sesión (evita crecimiento ilimitado)
_MAX_NOTIFICACIONES = 5


# ── Helpers ───────────────────────────────────────────────────────────────────


def _verificar_lider():
    """Retorna True si el usuario tiene el grupo de Líder."""
    return request.env.user.has_group("digitalizacion.group_digitalizacion_lider")


def _verificar_lider_raise():
    """Verifica grupo Líder y lanza AccessError si no lo tiene."""
    if not _verificar_lider():
        raise AccessError(
            _("No tienes permisos para acceder al módulo de digitalización.")
        )


def _get_asignaciones_activas(lider_id):
    """Retorna asignaciones activas del líder con proyecto activo."""
    return (
        request.env["digitalizacion.asignacion"]
        .sudo()
        .search(
            [
                ("lider_id", "=", lider_id),
                ("active", "=", True),
                ("proyecto_id.active", "=", True),
                ("proyecto_id.state", "=", "activo"),
            ]
        )
    )


def _get_proyecto_del_lider(proyecto_id, lider_id):
    """
    Obtiene el proyecto si el líder tiene asignación activa sobre él.
    Retorna el recordset del proyecto o None.
    """
    asig = (
        request.env["digitalizacion.asignacion"]
        .sudo()
        .search(
            [
                ("lider_id", "=", lider_id),
                ("proyecto_id", "=", proyecto_id),
                ("active", "=", True),
                ("proyecto_id.active", "=", True),
                ("proyecto_id.state", "=", "activo"),
            ],
            limit=1,
        )
    )
    return asig.proyecto_id if asig else None


def _verificar_acceso_proyecto(proyecto_id, lider_id):
    """Verifica acceso y retorna el proyecto. Lanza AccessError si no tiene acceso."""
    proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
    if not proyecto:
        raise AccessError(_("No tienes acceso al proyecto solicitado o no existe."))
    return proyecto


def _calcular_kpis(lider_id, domain_extra=None):
    """Delega cálculo de KPIs al modelo."""
    return (
        request.env["digitalizacion.registro"]
        .sudo()
        .get_kpis_lider(lider_id, domain_extra=domain_extra)
    )


def _add_notification(type_, message):
    """Agrega notificación a la sesión. Tipo: info, success, warning, danger."""
    if "notifications" not in request.session:
        request.session["notifications"] = []
    notifs = request.session["notifications"]
    if len(notifs) < _MAX_NOTIFICACIONES:
        notifs.append({"type": type_, "message": message})


def _build_date_domain(periodo, fecha_desde, fecha_hasta):
    """
    Construye dominio de fechas según el período seleccionado.
    Retorna (domain, periodo_actual_str).
    """
    hoy = date.today()

    if periodo == "hoy":
        return (
            [("fecha", "=", hoy)],
            _("Hoy · %s", hoy.strftime("%d/%m/%Y")),
        )

    if periodo == "semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        return (
            [("fecha", ">=", inicio), ("fecha", "<=", hoy)],
            _("Esta semana · desde %s", inicio.strftime("%d/%m/%Y")),
        )

    if periodo == "custom" and fecha_desde and fecha_hasta:
        try:
            desde = fields.Date.from_string(fecha_desde)
            hasta = fields.Date.from_string(fecha_hasta)
            return (
                [("fecha", ">=", desde), ("fecha", "<=", hasta)],
                _("%s — %s", desde.strftime("%d/%m/%Y"), hasta.strftime("%d/%m/%Y")),
            )
        except Exception:
            _logger.warning(
                "Fechas custom inválidas: %s - %s", fecha_desde, fecha_hasta
            )

    # Default: mes actual
    inicio_mes = hoy.replace(day=1)
    return (
        [("fecha", ">=", inicio_mes), ("fecha", "<=", hoy)],
        _("Este mes · %s", hoy.strftime("%B %Y")),
    )


def _get_resumen_etapas(proyecto_id, domain):
    """
    Resumen de producción por etapa para el dashboard.
    Usa _read_group para eficiencia.
    """
    Registro = request.env["digitalizacion.registro"].sudo()
    datos = Registro._read_group(
        domain=domain,
        groupby=["etapa_id"],
        aggregates=["produccion_principal:sum"],
    )
    if not datos:
        return []

    max_val = max((total or 0) for _, total in datos) or 1
    return [
        {
            "nombre": etapa.name or "Sin etapa",
            "cantidad": total or 0,
            "porcentaje": round(((total or 0) / max_val) * 100),
        }
        for etapa, total in sorted(datos, key=lambda x: x[0].sequence)
    ]


# ── Controlador principal ─────────────────────────────────────────────────────


class DigitalizacionPortal(http.Controller):
    # ── Dashboard ─────────────────────────────────────────────────────────────

    @http.route(
        "/digitalizacion/v1/dashboard",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def dashboard(self, **kwargs):
        """Dashboard principal del Líder con KPIs y registros recientes."""
        try:
            _verificar_lider_raise()
        except AccessError:
            _add_notification(
                "danger", _("Acceso denegado. Se requiere el rol de Líder de Proyecto.")
            )
            return request.redirect("/web/login")

        lider_id = request.env.user.id
        asignaciones = _get_asignaciones_activas(lider_id)

        if not asignaciones:
            return request.render(
                "digitalizacion.digitalizacion_portal_dashboard",
                {
                    "asignaciones": [],
                    "notifications": request.session.pop("notifications", []),
                    "page_name": "digitalizacion_dashboard",
                    "periodo_actual": _("Sin proyectos asignados"),
                    "proyecto_actual": None,
                },
            )

        # Proyecto activo — desde query param o el primero disponible
        try:
            proyecto_id = int(kwargs.get("proyecto_id", asignaciones[0].proyecto_id.id))
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except (ValueError, TypeError, AccessError):
            proyecto = asignaciones[0].proyecto_id

        periodo = kwargs.get("periodo", "mes")
        fecha_desde = kwargs.get("fecha_desde", "")
        fecha_hasta = kwargs.get("fecha_hasta", "")
        page = max(1, int(kwargs.get("page", 1) or 1))
        limit = 10

        date_domain, periodo_actual = _build_date_domain(
            periodo, fecha_desde, fecha_hasta
        )
        domain_final = date_domain + [("proyecto_id", "=", proyecto.id)]

        kpis = _calcular_kpis(lider_id, domain_final)
        resumen_etapas = _get_resumen_etapas(proyecto.id, domain_final)

        Registro = request.env["digitalizacion.registro"].sudo()
        ultimos_registros = Registro.search(
            [("lider_id", "=", lider_id)] + domain_final,
            order="fecha desc, id desc",
            offset=(page - 1) * limit,
            limit=limit,
        )

        return request.render(
            "digitalizacion.digitalizacion_portal_dashboard",
            {
                "kpis": kpis,
                "ultimos_registros": ultimos_registros,
                "asignaciones": asignaciones,
                "proyecto_actual": proyecto,
                "resumen_etapas": resumen_etapas,
                "periodo_actual": periodo_actual,
                "periodo": periodo,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
                "page": page,
                "has_next": len(ultimos_registros) == limit,
                "has_prev": page > 1,
                "notifications": request.session.pop("notifications", []),
                "page_name": "digitalizacion_dashboard",
            },
        )

    # ── Formulario de registro ────────────────────────────────────────────────

    @http.route(
        "/digitalizacion/v1/proyectos/<int:proyecto_id>/form",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def formulario_registro(self, proyecto_id, **kwargs):
        """Formulario para registrar producción diaria."""
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            _add_notification("danger", str(e))
            return request.redirect("/digitalizacion/v1/dashboard")

        etapas = (
            request.env["digitalizacion.etapa"]
            .sudo()
            .search([("active", "=", True)], order="sequence asc")
        )
        # Miembros activos del proyecto sin fecha de salida
        miembros = (
            request.env["digitalizacion.miembro_proyecto"]
            .sudo()
            .search(
                [
                    ("proyecto_id", "=", proyecto_id),
                    ("active", "=", True),
                    ("fecha_salida", "=", False),
                ],
                order="partner_name asc",
            )
        )

        escaneres = (
            request.env["digitalizacion.tipo_escaner"]
            .sudo()
            .search([("active", "=", True)], order="name asc")
        )

        return request.render(
            "digitalizacion.digitalizacion_portal_registro_form",
            {
                "proyecto": proyecto,
                "etapas_json": json.dumps(
                    [{"id": e.id, "name": e.name} for e in etapas]
                ),
                "miembros_json": json.dumps(
                    [{"id": m.id, "name": m.partner_name} for m in miembros]
                ),
                "escaneres_json": json.dumps(
                    [{"id": e.id, "name": e.name} for e in escaneres]
                ),
                "notifications": request.session.pop("notifications", []),
                "page_name": "digitalizacion_formulario",
            },
        )

    # ── Detalle del proyecto ──────────────────────────────────────────────────

    @http.route(
        "/digitalizacion/v1/proyectos/<int:proyecto_id>",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def proyecto_detalle(self, proyecto_id, **kwargs):
        """Vista de detalle del proyecto con progreso y accesos rápidos."""
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            _add_notification("danger", str(e))
            return request.redirect("/digitalizacion/v1/dashboard")

        return request.render(
            "digitalizacion.digitalizacion_portal_proyecto_detalle",
            {
                "proyecto": proyecto,
                "notifications": request.session.pop("notifications", []),
                "page_name": "digitalizacion_proyecto",
            },
        )

    # ── Vista de miembros (solo lectura + gráfico) ────────────────────────────

    @http.route(
        "/digitalizacion/v1/proyectos/<int:proyecto_id>/miembros",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def proyecto_miembros(self, proyecto_id, **kwargs):
        """
        Lista de miembros del equipo (solo lectura) con gráfico de
        participación por etapa (barras apiladas + tabla heatmap).
        El líder no puede agregar ni dar de baja miembros — eso es
        responsabilidad del Administrador desde el backoffice.
        """
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            _add_notification("danger", str(e))
            return request.redirect("/digitalizacion/v1/dashboard")

        miembros = (
            request.env["digitalizacion.miembro_proyecto"]
            .sudo()
            .search(
                [
                    ("proyecto_id", "=", proyecto_id),
                    ("active", "=", True),
                ],
                order="partner_name asc",
            )
        )

        # Datos para el gráfico de participación
        participacion = (
            request.env["digitalizacion.registro"]
            .sudo()
            .get_participacion_equipo(proyecto_id)
        )

        # Colores para las etapas (en orden de sequence)
        colores_etapa = [
            "#378ADD",  # Limpieza — azul
            "#639922",  # Ordenado — verde
            "#1D9E75",  # Digitalizado — teal
            "#EF9F27",  # Editado — ámbar
            "#7F77DD",  # Indexado — púrpura
        ]
        etapas_con_color = [
            {"nombre": etapa, "color": colores_etapa[i % len(colores_etapa)]}
            for i, etapa in enumerate(participacion.get("etapas", []))
        ]

        return request.render(
            "digitalizacion.digitalizacion_portal_miembros_equipo",
            {
                "proyecto": proyecto,
                "miembros": miembros,
                "participacion": participacion,
                "etapas_con_color": etapas_con_color,
                "notifications": request.session.pop("notifications", []),
                "page_name": "digitalizacion_miembros",
            },
        )

    # ── API POST: guardar registros ───────────────────────────────────────────

    @http.route(
        "/digitalizacion/api/v1/proyectos/<int:proyecto_id>/registros",
        type="json",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def api_guardar_registros(self, proyecto_id, **kwargs):
        """
        Guarda un lote de registros de producción.
        Payload esperado: { "fecha": "YYYY-MM-DD", "filas": [...] }
        """
        if not _verificar_lider():
            return {
                "success": False,
                "error": {"message": _("Acceso denegado. Se requiere grupo Líder.")},
            }

        lider_id = request.env.user.id
        proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
        if not proyecto:
            return {
                "success": False,
                "error": {"message": _("Proyecto no encontrado o sin acceso.")},
            }

        filas = kwargs.get("filas", [])
        fecha = kwargs.get("fecha")

        if not filas or not fecha:
            return {
                "success": False,
                "error": {
                    "message": _("Datos incompletos. Se requieren fecha y filas.")
                },
            }

        try:
            records_vals = []
            for v in filas:
                records_vals.append(
                    {
                        "proyecto_id": proyecto_id,
                        "fecha": fecha,
                        "miembro_id": v.get("miembro_id"),
                        "etapa_id": v.get("etapa_id"),
                        # Campos de caja y expedientes
                        "referencia_cajas": v.get("referencia_cajas"),
                        "no_expedientes": v.get("no_expedientes", 0),
                        "total_folios": v.get("total_folios", 0),
                        # Campos de digitalizado
                        "total_escaneos": v.get("total_escaneos", 0),
                        "tipo_escaner_ids": [(6, 0, v.get("tipo_escaner_ids", []))],
                        # Campos de editado
                        "expedientes_editados": v.get("expedientes_editados", 0),
                        "folios_editados": v.get("folios_editados", 0),
                        # Campos de indexado
                        "expedientes_indexados": v.get("expedientes_indexados", 0),
                        "folios_indexados": v.get("folios_indexados", 0),
                        # Campo común
                        "observacion": v.get("observacion"),
                        # lider_id NO se pasa — el modelo lo fuerza en create()
                    }
                )

            if records_vals:
                # Crear con el entorno del líder (no sudo) para que
                # el override de create() asigne lider_id correctamente
                request.env["digitalizacion.registro"].create(records_vals)

            return {"success": True}

        except (ValidationError, UserError) as e:
            # Errores de validación de negocio — mostrar al usuario
            return {"success": False, "error": {"message": str(e)}}
        except Exception:
            # Errores técnicos — loggear sin exponer detalles internos
            _logger.exception(
                "Error inesperado al guardar registros para proyecto %d", proyecto_id
            )
            return {
                "success": False,
                "error": {"message": _("Error interno. Contacta al administrador.")},
            }


# ── Extensión del portal home ─────────────────────────────────────────────────


class DigitalizacionPortalHome(CustomerPortal):
    """Agrega contador de digitalización al portal home de Odoo."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("digitalizacion.group_digitalizacion_lider"):
            values["digitalizacion_count"] = (
                request.env["digitalizacion.registro"]
                .sudo()
                .search_count([("lider_id", "=", request.env.user.id)])
            )
        else:
            values["digitalizacion_count"] = 0
        return values
