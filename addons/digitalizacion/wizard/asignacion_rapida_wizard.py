# -*- coding: utf-8 -*-
from odoo import models, fields

class AsignacionRapidaWizard(models.TransientModel):
    _name = 'digitalizacion.asignacion_rapida_wizard'
    _description = 'Wizard de Asignación Rápida de Miembro a Proyecto'

    proyecto_id = fields.Many2one(
        'digitalizacion.proyecto',
        string="Proyecto",
        required=True,
        domain=[('state', '=', 'activo')]
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Contacto / Digitalizador",
        required=True
    )
    fecha_ingreso = fields.Date(
        string="Fecha de Asignación",
        default=fields.Date.context_today,
        required=True
    )

    def action_asignar_miembro(self):
        """
        Crea un registro de digitalizacion.miembro_proyecto directamente.
        Se accede típicamente desde un botón en la vista del Admin.
        """
        self.ensure_one()
        Miembro = self.env['digitalizacion.miembro_proyecto']

        # Verificamos si ya existe la asignación
        existente = Miembro.search([
            ('proyecto_id', '=', self.proyecto_id.id),
            ('partner_id', '=', self.partner_id.id)
        ], limit=1)

        if existente:
            # Si existe pero está inactivo, lo reactivamos
            if not existente.active:
                existente.write({
                    'active': True,
                    'fecha_salida': False,
                    'fecha_ingreso': self.fecha_ingreso
                })
        else:
            # Crear nueva asignación
            Miembro.create({
                'proyecto_id': self.proyecto_id.id,
                'partner_id': self.partner_id.id,
                'fecha_ingreso': self.fecha_ingreso,
                'active': True
            })

        return {'type': 'ir.actions.act_window_close'}
