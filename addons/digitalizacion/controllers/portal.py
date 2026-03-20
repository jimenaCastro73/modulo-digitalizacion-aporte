# -*- coding: utf-8 -*-
"""
portal.py — Vistas HTTP del portal del Líder
Módulo de Gestión de Digitalización · Odoo 17 · OTEC GLOBAL
"""

import json
import logging
from datetime import date, timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

# ===========================================================================
# SERVICIOS (lógica de negocio separada)
# ===========================================================================

class DashboardService:
    """Servicio para lógica del dashboard"""
    
    def __init__(self, lider_id, proyecto_ref):
        self.lider_id = lider_id
        self.proyecto = proyecto_ref
        
    def build_date_domain(self, periodo, fecha_desde, fecha_hasta):
        """Construye dominio de fechas según período"""
        hoy = date.today()
        domain = []
        periodo_actual = ""
        
        if periodo == "hoy":
            domain = [("fecha", "=", hoy)]
            periodo_actual = f"Hoy · {hoy.strftime('%d/%m/%Y')}"
        elif periodo == "semana":
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            domain = [("fecha", ">=", inicio_semana), ("fecha", "<=", hoy)]
            periodo_actual = f"Esta semana · desde {inicio_semana.strftime('%d/%m/%Y')}"
        elif periodo == "custom" and fecha_desde and fecha_hasta:
            try:
                desde = fields.Date.from_string(fecha_desde)
                hasta = fields.Date.from_string(fecha_hasta)
                domain = [("fecha", ">=", desde), ("fecha", "<=", hasta)]
                periodo_actual = f"{desde.strftime('%d/%m/%Y')} — {hasta.strftime('%d/%m/%Y')}"
            except Exception:
                _logger.warning("Fechas custom inválidas: %s - %s", fecha_desde, fecha_hasta)
                domain = []
        else:
            inicio_mes = hoy.replace(day=1)
            domain = [("fecha", ">=", inicio_mes), ("fecha", "<=", hoy)]
            periodo_actual = f"Este mes · {hoy.strftime('%B %Y')}"
            
        return domain, periodo_actual
    
    def get_summary_by_stage(self, domain):
        """Resumen de producción por etapa"""
        Registro = request.env["digitalizacion.registro"].sudo()
        conteo = {}
        
        for rec in Registro.search(domain):
            nombre = rec.etapa_id.name or "Sin etapa"
            conteo[nombre] = conteo.get(nombre, 0) + (rec.produccion_principal or 0)
            
        if not conteo:
            return []
            
        max_val = max(conteo.values()) or 1
        return [{
            "nombre": nombre,
            "cantidad": cantidad,
            "porcentaje": round((cantidad / max_val) * 100),
        } for nombre, cantidad in sorted(conteo.items())]
    
    def get_recent_records(self, domain, page=1, limit=20):
        """Registros recientes con paginación"""
        Registro = request.env["digitalizacion.registro"].sudo()
        return Registro.search(
            [("lider_id", "=", self.lider_id)] + domain,
            order="fecha desc, id desc",
            offset=(page-1)*limit,
            limit=limit
        )

# ===========================================================================
# HELPERS (compartidos)
# ===========================================================================

def _verificar_lider():
    """Verifica permisos de líder"""
    if not request.env.user.has_group("digitalizacion.group_digitalizacion_lider"):
        return False
    return True

def _verificar_lider_raise():
    """Verifica permisos de líder y lanza excepción si falla"""
    if not _verificar_lider():
        raise AccessError(_("No tienes permisos para acceder al módulo de digitalización."))

def _get_asignaciones_activas(lider_id: int):
    """Retorna asignaciones activas del líder"""
    return request.env["digitalizacion.asignacion"].sudo().search([
        ("lider_id", "=", lider_id),
        ("active", "=", True),
        ("proyecto_id.active", "=", True),
        ("proyecto_id.state", "=", "activo"),
    ])

def _get_proyecto_del_lider(proyecto_id: int, lider_id: int):
    """Obtiene proyecto si pertenece al líder"""
    asig = request.env["digitalizacion.asignacion"].sudo().search([
        ("lider_id", "=", lider_id),
        ("proyecto_id", "=", proyecto_id),
        ("active", "=", True),
        ("proyecto_id.active", "=", True),
        ("proyecto_id.state", "=", "activo"),
    ], limit=1)
    return asig.proyecto_id if asig else None

def _verificar_acceso_proyecto(proyecto_id, lider_id):
    """Verifica que el líder tenga acceso al proyecto específico"""
    proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
    if not proyecto:
        raise AccessError(_("No tienes acceso al proyecto solicitado o no existe."))
    return proyecto

def _calcular_kpis(lider_id: int, domain_extra: list = None) -> dict:
    """Delega cálculo de KPIs al modelo"""
    return request.env["digitalizacion.registro"].sudo().get_kpis_lider(
        lider_id, domain_extra=domain_extra
    )

def _add_notification(req, type_, message):
    """Agrega notificación a la sesión de Odoo. Tipo: info, success, warning, danger"""
    if 'notifications' not in req.session:
        req.session['notifications'] = []
    req.session['notifications'].append({
        'type': type_,
        'message': message
    })

# ===========================================================================
# CONTROLADOR PRINCIPAL
# ===========================================================================

class DigitalizacionPortal(http.Controller):
    
    # =========================================================================
    # VISTAS (GET)
    # =========================================================================
    
    @http.route("/digitalizacion/v1/dashboard", type="http", auth="user", website=True, methods=["GET"])
    def dashboard(self, **kwargs):
        """Dashboard principal del Líder"""
        try:
            _verificar_lider_raise()
        except AccessError:
            _add_notification(request, 'danger', _("Acceso denegado. Se requiere el rol de Líder de Proyecto."))
            return request.redirect("/web/login")
            
        lider_id = request.env.user.id
        asignaciones = _get_asignaciones_activas(lider_id)
        
        if not asignaciones:
            return request.render("digitalizacion.digitalizacion_portal_dashboard", {
                "asignaciones": [],
                "notifications": request.session.pop('notifications', []),
                "page_name": "digitalizacion_dashboard",
                "periodo_actual": _("Sin proyectos asignados"),
                "proyecto_actual": None
            })
            
        try:
            proyecto_id = int(kwargs.get("proyecto_id", asignaciones[0].proyecto_id.id))
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except (ValueError, TypeError, AccessError):
            proyecto = asignaciones[0].proyecto_id
            
        service = DashboardService(lider_id, proyecto)
        periodo = kwargs.get("periodo", "mes")
        fecha_desde = kwargs.get("fecha_desde", "")
        fecha_hasta = kwargs.get("fecha_hasta", "")
        page = max(1, int(kwargs.get("page", 1)))
        limit = 10
        
        date_domain, periodo_actual = service.build_date_domain(periodo, fecha_desde, fecha_hasta)
        domain_final = date_domain + [("proyecto_id", "=", proyecto.id)]
        
        kpis = _calcular_kpis(lider_id, domain_final)
        ultimos_registros = service.get_recent_records(domain_final, page=page, limit=limit)
        resumen_etapas = service.get_summary_by_stage(domain_final)
        has_next = len(ultimos_registros) == limit

        return request.render("digitalizacion.digitalizacion_portal_dashboard", {
            "kpis": kpis,
            "ultimos_registros": ultimos_registros,
            "asignaciones": asignaciones,
            "proyecto_actual": proyecto,
            "resumen_etapas": resumen_etapas,
            "periodo_actual": periodo_actual,
            "page": page,
            "has_next": has_next,
            "has_prev": page > 1,
            "notifications": request.session.pop('notifications', []),
            "page_name": "digitalizacion_dashboard",
        })

    @http.route("/digitalizacion/v1/proyectos/<int:proyecto_id>/form", type="http", auth="user", website=True, methods=["GET"])
    def formulario_registro(self, proyecto_id, **kwargs):
        """Formulario para registrar producción"""
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            _add_notification(request, 'danger', str(e))
            return request.redirect("/digitalizacion/v1/dashboard")
            
        etapas = request.env["digitalizacion.etapa"].sudo().search([("active", "=", True)], order="sequence asc")
        miembros = request.env["digitalizacion.miembro_proyecto"].sudo().search([
            ("proyecto_id", "=", proyecto_id),
            ("active", "=", True),
            ("fecha_salida", "=", False),
        ], order="partner_name asc")
        escaneres = request.env["digitalizacion.tipo_escaner"].sudo().search([("active", "=", True)], order="name asc")
        
        return request.render("digitalizacion.digitalizacion_portal_registro_form", {
            "proyecto": proyecto,
            "etapas_json": json.dumps([{"id": e.id, "name": e.name} for e in etapas]),
            "miembros_json": json.dumps([{"id": m.id, "name": m.partner_name} for m in miembros]),
            "escaneres_json": json.dumps([{"id": e.id, "name": e.name} for e in escaneres]),
            "notifications": request.session.pop('notifications', []),
            "page_name": "digitalizacion_formulario",
        })

    @http.route("/digitalizacion/v1/proyectos/<int:proyecto_id>", type="http", auth="user", website=True, methods=["GET"])
    def proyecto_detalle(self, proyecto_id, **kwargs):
        """Detalle del proyecto"""
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            _add_notification(request, 'danger', str(e))
            return request.redirect("/digitalizacion/v1/dashboard")
            
        return request.render("digitalizacion.digitalizacion_portal_proyecto_detalle", {
            "proyecto": proyecto,
            "notifications": request.session.pop('notifications', []),
            "page_name": "digitalizacion_proyecto",
        })

    @http.route("/digitalizacion/v1/proyectos/<int:proyecto_id>/miembros", type="http", auth="user", website=True, methods=["GET"])
    def proyecto_miembros(self, proyecto_id, **kwargs):
        """Gestión de miembros del equipo"""
        try:
            _verificar_lider_raise()
            lider_id = request.env.user.id
            proyecto = _verificar_acceso_proyecto(proyecto_id, lider_id)
        except AccessError as e:
            _add_notification(request, 'danger', str(e))
            return request.redirect("/digitalizacion/v1/dashboard")
            
        miembros = request.env["digitalizacion.miembro_proyecto"].sudo().search([
            ("proyecto_id", "=", proyecto_id),
            ("active", "=", True),
        ], order="partner_name asc")
        
        return request.render("digitalizacion.digitalizacion_portal_miembros_equipo", {
            "proyecto": proyecto,
            "miembros": miembros,
            "notifications": request.session.pop('notifications', []),
            "page_name": "digitalizacion_miembros",
        })

    # =========================================================================
    # ACCIONES API (POST, JSON)
    # =========================================================================

    @http.route('/digitalizacion/api/v1/proyectos/<int:proyecto_id>/registros', type='json', auth='user', website=True, methods=['POST'], csrf=True)
    def api_guardar_registros(self, proyecto_id, **kwargs):
        """Guarda un lote de registros de producción"""
        if not _verificar_lider():
            return {'success': False, 'error': {'message': _("Acceso denegado. Se requiere grupo Líder.")}}

        lider_id = request.env.user.id
        proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
        if not proyecto:
            return {'success': False, 'error': {'message': _("Proyecto no encontrado o sin acceso.")}}

        vals_list = kwargs.get('filas', [])
        fecha = kwargs.get('fecha')
        if not vals_list or not fecha:
            return {'success': False, 'error': {'message': _("Datos incompletos.")}}

        try:
            records_vals = []
            for v in vals_list:
                rv = {
                    'proyecto_id': proyecto_id,
                    'lider_id': lider_id,
                    'fecha': fecha,
                    'miembro_id': v.get('miembro_id'),
                    'etapa_id': v.get('etapa_id'),
                    'no_caja': v.get('no_caja'),
                    'cantidad_cajas': v.get('cantidad_cajas', 0),
                    'no_expedientes': v.get('no_expedientes', 0),
                    'total_folios': v.get('total_folios', 0),
                    'total_escaneos': v.get('total_escaneos', 0),
                    'expedientes_editados': v.get('expedientes_editados', 0),
                    'folios_editados': v.get('folios_editados', 0),
                    'expedientes_indexados': v.get('expedientes_indexados', 0),
                    'folios_indexados': v.get('folios_indexados', 0),
                    'observacion': v.get('observacion'),
                    'tipo_escaner_ids': [(6, 0, v.get('tipo_escaner_ids', []))]
                }
                records_vals.append(rv)

            if records_vals:
                request.env['digitalizacion.registro'].sudo().create(records_vals)
            return {'success': True}

        except Exception as e:
            _logger.error("Error al guardar registros: %s", str(e))
            return {'success': False, 'error': {'message': str(e)}}

    @http.route('/digitalizacion/api/v1/partners/search', type='json', auth='user', website=True, methods=['POST'], csrf=True)
    def api_search_partners(self, term, proyecto_id=None, **kwargs):
        """Busca partners para agregar como miembros"""
        if not _verificar_lider():
            return {'success': False, 'error': {'message': _("Acceso denegado.")}}

        domain = [('name', 'ilike', term)]
        if proyecto_id:
            miembros = request.env['digitalizacion.miembro_proyecto'].sudo().search([('proyecto_id', '=', proyecto_id)])
            partner_ids = miembros.mapped('partner_id').ids
            domain.append(('id', 'not in', partner_ids))

        partners = request.env['res.partner'].sudo().search(domain, limit=10)
        data = [{'id': p.id, 'name': p.name, 'email': p.email} for p in partners]
        return {'success': True, 'data': data}

    @http.route('/digitalizacion/api/v1/proyectos/<int:proyecto_id>/miembros', type='json', auth='user', website=True, methods=['POST'], csrf=True)
    def api_agregar_miembro(self, proyecto_id, partner_id=None, nombre_nuevo=None, **kwargs):
        """Agrega un miembro al proyecto"""
        if not _verificar_lider():
            return {'success': False, 'error': {'message': _("Acceso denegado.")}}

        lider_id = request.env.user.id
        proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
        if not proyecto:
            return {'success': False, 'error': {'message': _("Proyecto no encontrado.")}}

        try:
            if not partner_id and nombre_nuevo:
                partner = request.env['res.partner'].sudo().create({'name': nombre_nuevo, 'company_type': 'person'})
                partner_id = partner.id
            
            if not partner_id:
                return {'success': False, 'error': {'message': _("Falta el partner o nombre.")}}

            existente = request.env['digitalizacion.miembro_proyecto'].sudo().search([
                ('proyecto_id', '=', proyecto_id),
                ('partner_id', '=', partner_id)
            ], limit=1)
            
            if existente:
                if existente.active:
                    return {'success': False, 'error': {'message': _("Este contacto ya es miembro activo del proyecto.")}}
                else:
                    existente.active = True
                    return {'success': True}

            request.env['digitalizacion.miembro_proyecto'].sudo().create({
                'proyecto_id': proyecto_id,
                'partner_id': partner_id,
                'fecha_integracion': fields.Date.today()
            })
            return {'success': True}

        except Exception as e:
            return {'success': False, 'error': {'message': str(e)}}


class DigitalizacionPortalHome(CustomerPortal):
    """Extiende el portal home con contador de digitalización"""
    
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("digitalizacion.group_digitalizacion_lider"):
            values["digitalizacion_count"] = request.env["digitalizacion.registro"].sudo().search_count([
                ("lider_id", "=", request.env.user.id)
            ])
        else:
            values["digitalizacion_count"] = 0
        return values
