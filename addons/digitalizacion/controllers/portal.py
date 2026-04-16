# -*- coding: utf-8 -*-
"""
portal.py — Controller HTTP del portal del Líder
Módulo de Gestión de Digitalización · Odoo 17

CAMBIOS DRY/KISS respecto a la versión original:
  - _sanitizar_entero, _sanitizar_texto, _validar_fila → eliminadas.
    Ahora viven en utils.py y registro.py respectivamente.
  - _get_resumen_etapas → eliminada. Ahora es registro.get_resumen_etapas().
  - api_guardar_registros → llama a registro.validar_fila_api() en vez
    de validar inline. El controlador solo habla HTTP.
  - Las constantes MAX_* se importan desde tools/constantes.py.

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
"""

import json
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, fields, http
from odoo.tools.misc import format_date
# from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..tools.constantes import MAX_FILAS, MAX_NOTIFICACIONES

_logger = logging.getLogger(__name__)


# ── Helpers de acceso y sesión ────────────────────────────────────────────────


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


def _add_notification(type_, message):
    """Agrega notificación a la sesión. Tipo: info, success, warning, danger."""
    if "notifications" not in request.session:
        request.session["notifications"] = []
    notifs = request.session["notifications"]
    if len(notifs) < MAX_NOTIFICACIONES:
        notifs.append({"type": type_, "message": message})


def _build_date_domain(periodo, fecha_desde, fecha_hasta):
    """
    Construye dominio de fechas según el período seleccionado.
    Retorna (domain, periodo_actual_str).
    """
    hoy = fields.Date.context_today(request.env.user)

    if periodo == "hoy":
        return (
            [("fecha", "=", hoy)],
            _("Hoy · %s", format_date(request.env, hoy, date_format="dd/MM/yyyy")),
        )

    if periodo == "semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        return (
            [("fecha", ">=", inicio), ("fecha", "<=", hoy)],
            _(
                "Esta semana · desde %s",
                format_date(request.env, inicio, date_format="dd/MM/yyyy"),
            ),
        )

    if periodo == "custom" and fecha_desde and fecha_hasta:
        try:
            desde = fields.Date.from_string(fecha_desde)
            hasta = fields.Date.from_string(fecha_hasta)
            if desde > hasta:
                raise ValueError("fecha_desde posterior a fecha_hasta")
            if hasta > hoy:
                hasta = hoy
            return (
                [("fecha", ">=", desde), ("fecha", "<=", hasta)],
                _(
                    "%s — %s",
                    format_date(request.env, desde, date_format="dd/MM/yyyy"),
                    format_date(request.env, hasta, date_format="dd/MM/yyyy"),
                ),
            )
        except Exception as e:
            _logger.warning(
                "Fechas custom inválidas: %s - %s. Error: %s",
                fecha_desde,
                fecha_hasta,
                e,
            )

    # Caso default: mes actual (SIEMPRE debe retornar algo)
    inicio_mes = hoy.replace(day=1)
    return (
        [("fecha", ">=", inicio_mes), ("fecha", "<=", hoy)],
        _(
            "Este mes · %s",
            format_date(request.env, hoy, date_format="MMMM yyyy"),
        ),
    )


# ── Respuesta JSON estandarizada ──────────────────────────────────────────────


def _json_ok(data=None):
    return request.make_json_response({"ok": True, **(data or {})})


def _json_error(mensaje, status=400):
    return request.make_json_response({"ok": False, "error": mensaje}, status=status)


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

        try:
            proyecto_id = int(kwargs.get("proyecto_id", asignaciones[0].proyecto_id.id))
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except (ValueError, TypeError, AccessError):
            proyecto = asignaciones[0].proyecto_id

        periodo = kwargs.get("periodo", "mes")
        fecha_desde = kwargs.get("fecha_desde", "")
        fecha_hasta = kwargs.get("fecha_hasta", "")
        numero_pagina = max(1, int(kwargs.get("page", 1) or 1))
        limit = 10

        # Obtener dominio de fechas
        date_domain, periodo_actual = _build_date_domain(
            periodo, fecha_desde, fecha_hasta
        )
        domain_final = date_domain + [("proyecto_id", "=", proyecto.id)]

        Registro = request.env["digitalizacion.registro"].sudo()

        # KPIs usando el método del modelo
        kpis = Registro.get_kpis_lider(lider_id, domain_final)

        # Resumen por etapas - método del modelo
        resumen_etapas = Registro.get_resumen_etapas(domain_final)

        # Últimos registros
        ultimos_registros = Registro.search(
            [("lider_id", "=", lider_id)] + domain_final,
            order="fecha desc, id desc",
            offset=(numero_pagina - 1) * limit,
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
                "page": numero_pagina,
                "has_next": len(ultimos_registros) == limit,
                "has_prev": numero_pagina > 1,
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
            if proyecto.state != "en_curso":
                _add_notification(
                    "warning",
                    _(
                        "El proyecto '%s' está en pausa o finalizado. No se puede registrar nueva producción.",
                        proyecto.name,
                    ),
                )
                return request.redirect(
                    "/digitalizacion/v1/dashboard?proyecto_id=%s" % proyecto.id
                )
        except AccessError as e:
            _add_notification("danger", str(e))
            return request.redirect("/digitalizacion/v1/dashboard")

        etapas = (
            request.env["digitalizacion.etapa"]
            .sudo()
            .search([("active", "=", True)], order="sequence asc")
        )
        miembros = (
            request.env["digitalizacion.miembro_proyecto"]
            .sudo()
            .search(
                [
                    ("proyecto_id", "=", proyecto.id),
                    ("active", "=", True),
                    ("fecha_salida", "=", False),
                ]
            )
        )
        escaneres = (
            request.env["digitalizacion.tipo_escaner"]
            .sudo()
            .search([("active", "=", True)])
        )

        return request.render(
            "digitalizacion.digitalizacion_portal_registro_form",
            {
                "proyecto": proyecto,
                "proyecto_actual": proyecto,
                "etapas_json": Markup(
                    json.dumps([{"id": e.id, "name": e.name} for e in etapas])
                ),
                "miembros_json": Markup(
                    json.dumps([{"id": m.id, "name": m.partner_name} for m in miembros])
                ),
                "escaneres_json": Markup(
                    json.dumps([{"id": e.id, "name": e.name} for e in escaneres])
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
                "proyecto_actual": proyecto,
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

        # Datos para el gráfico de participación (método del modelo)
        Registro = request.env["digitalizacion.registro"].sudo()
        participacion = Registro.get_participacion_equipo(proyecto_id)

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
                "proyecto_actual": proyecto,
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
        methods=["POST"],
    )
    def api_guardar_registros(self, proyecto_id, **kwargs):
        """
        Recibe payload JSON con una lista de filas de producción y las persiste.
        Odoo 17 extrae automáticamente de 'params' a 'kwargs'
        """
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            # Para errores de acceso, Odoo espera un dict con 'error'
            return {"success": False, "error": str(e)}

        # Con type='json', los datos están en kwargs directamente
        fecha = kwargs.get("fecha")
        filas = kwargs.get("registros", [])

        if not fecha:
            return {"error": _("Fecha requerida.")}

        # Validar formato de fecha y que no sea futura
        try:
            fecha_date = fields.Date.from_string(str(fecha))
            hoy = fields.Date.context_today(request.env.user)
            if fecha_date > hoy:
                return {"error": _("La fecha no puede ser futura (%s).", fecha)}
        except Exception:
            return {"error": _("Formato de fecha inválido. Use YYYY-MM-DD.")}

        if not isinstance(filas, list) or not filas:
            return {"error": _("Se requiere al menos una fila de datos.")}

        if len(filas) > MAX_FILAS:
            return {
                "error": _(
                    "Se permiten máximo %d filas por envío (recibidas: %d).",
                    MAX_FILAS,
                    len(filas),
                )
            }

        Registro = request.env["digitalizacion.registro"].sudo()
        ids_creados = []

        try:
            # Usamos una transacción para que si una fila falla, no se guarde nada
            for idx, fila in enumerate(filas, start=1):
                vals = Registro.validar_fila_api(fila, idx)
                vals.update(
                    {
                        "lider_id": lider_id,
                        "proyecto_id": proyecto.id,
                        "fecha": fecha,
                    }
                )
                nuevo = Registro.create(vals)
                ids_creados.append(nuevo.id)

        except ValidationError as e:
            # IMPORTANTE: Capturar el error de validación de Odoo
            return {"success": False, "error": str(e.args[0] if e.args else e)}
        except Exception:
            _logger.exception("Error inesperado en API portal")
            return {"success": False, "error": _("Error interno del servidor.")}

        return {"success": True, "ids": ids_creados, "total": len(ids_creados)}


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
