# -*- coding: utf-8 -*-
import logging
from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class DigitalizacionPortalPost(http.Controller):

    def _verificar_lider(self):
        """Verifica que el usuario sea Líder de Digitalización"""
        if not request.env.user.has_group('digitalizacion.group_digitalizacion_lider'):
            return False
        return True

    def _get_proyecto_del_lider(self, proyecto_id):
        """Valida que el líder tenga asignado el proyecto solicitado"""
        return request.env['digitalizacion.proyecto'].sudo().search([
            ('id', '=', proyecto_id),
            ('asignacion_ids.lider_id', '=', request.env.user.id),
            ('asignacion_ids.active', '=', True),
            ('active', '=', True),
            ('state', '=', 'activo')
        ], limit=1)

    @http.route('/digitalizacion/api/v1/proyectos/<int:proyecto_id>/registros', type='json', auth='user', website=True, methods=['POST'], csrf=True)
    def api_guardar_registros(self, proyecto_id, **kwargs):
        """
        Guarda un lote de registros de producción.
        Espera: { 'fecha': 'YYYY-MM-DD', 'filas': [...] }
        """
        if not self._verificar_lider():
            return {'success': False, 'error': {'message': _("Acceso denegado. Se requiere grupo Líder.")}}

        proyecto = self._get_proyecto_del_lider(proyecto_id)
        if not proyecto:
            return {'success': False, 'error': {'message': _("Proyecto no encontrado o sin acceso.")}}

        vals_list = kwargs.get('filas', [])
        fecha = kwargs.get('fecha')

        if not vals_list or not fecha:
            return {'success': False, 'error': {'message': _("Datos incompletos.")}}

        try:
            # Audit recommendation: lider_id should be request.env.user.id
            lider_id = request.env.user.id
            
            records_vals = []
            for v in vals_list:
                # Mapeo de campos según auditoría y JS
                # JS envía total_folios -> el modelo tiene cantidad_folios (según auditoría #10 pero walkthrough dice que se renombró a total_folios)
                # Vamos a verificar los campos del modelo digitalizacion.registro para estar seguros.
                
                # Basado en el renaming de Fase 7 (#4.1 de implementation_plan.md de bce49...):
                # nombre_caja -> no_caja
                # cantidad_expedientes -> no_expedientes
                # cantidad_folios -> total_folios
                # cantidad_escaneos -> total_escaneos
                
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
        """Busca partners para agregar como miembros (Audit #12: restringir a share=True si aplica, o simplemente res.partner)"""
        if not self._verificar_lider():
            return {'success': False, 'error': {'message': _("Acceso denegado.")}}

        domain = [('name', 'ilike', term)]
        # Si queremos evitar duplicados que ya están en el proyecto:
        if proyecto_id:
            miembros = request.env['digitalizacion.miembro_proyecto'].sudo().search([('proyecto_id', '=', proyecto_id)])
            partner_ids = miembros.mapped('partner_id').ids
            domain.append(('id', 'not in', partner_ids))

        partners = request.env['res.partner'].sudo().search(domain, limit=10)
        
        data = []
        for p in partners:
            data.append({
                'id': p.id,
                'name': p.name,
                'email': p.email
            })
        
        return {'success': True, 'data': data}

    @http.route('/digitalizacion/api/v1/proyectos/<int:proyecto_id>/miembros', type='json', auth='user', website=True, methods=['POST'], csrf=True)
    def api_agregar_miembro(self, proyecto_id, partner_id=None, nombre_nuevo=None, **kwargs):
        """Agrega un miembro al proyecto (creando el partner si es necesario)"""
        if not self._verificar_lider():
            return {'success': False, 'error': {'message': _("Acceso denegado.")}}

        proyecto = self._get_proyecto_del_lider(proyecto_id)
        if not proyecto:
            return {'success': False, 'error': {'message': _("Proyecto no encontrado.")}}

        try:
            if not partner_id and nombre_nuevo:
                # Crear nuevo partner
                partner = request.env['res.partner'].sudo().create({
                    'name': nombre_nuevo,
                    'company_type': 'person'
                })
                partner_id = partner.id
            
            if not partner_id:
                return {'success': False, 'error': {'message': _("Falta el partner o nombre.")}}

            # Verificar si ya existe
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
