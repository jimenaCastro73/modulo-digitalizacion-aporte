# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Digitalización',
    'version': '17.0.1.0.0',
    'category': 'Services',
    'summary': 'Gestión de proyectos de digitalización de documentos',
    'author': 'Jimena Castro — Práctica Profesional OTEC GLOBAL',
    'depends': ['base', 'contacts', 'website'],
    'data': [
        # 1. Seguridad primero: grupos, reglas y ACLs
        'security/security.xml',
        'security/ir.model.access.csv',

        # 2. Datos maestros iniciales
        'data/etapas_default.xml',

        # 3. Vistas y acciones (antes que los menús que las referencian)
        'views/admin/proyecto_views.xml',
        'views/admin/asignacion_views.xml',
        'views/operaciones/miembro_views.xml',
        'views/operaciones/registro_views.xml',
        'views/configuracion/etapa_views.xml',
        'views/configuracion/tipo_escaner_views.xml',
        'views/dashboard/dashboard_admin.xml',

        # 4. Menús (después de las acciones que referencian)
        'views/admin/menu_views.xml',
        'views/operaciones/menu_operaciones.xml',
        'views/configuracion/menu_configuracion.xml',

        # 5. Portal (vistas QWeb website)
        'views/portal/portal_home.xml',
        'views/portal/portal_proyecto.xml',
        'views/portal/portal_registro_form.xml',
        'views/portal/portal_miembros.xml',

        # 6. Wizards
        # (eliminados — funcionalidad cubierta por models, views y controllers nativos de Odoo)
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}