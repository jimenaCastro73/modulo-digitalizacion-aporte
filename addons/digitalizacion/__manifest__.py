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

        # 3. Vistas y acciones — Admin
        #    Orden: proyectos → operaciones → configuracion → dashboard
        #    (las acciones deben existir antes que menus.xml las referencie)
        'views/admin/proyectos/proyecto_views.xml',
        'views/admin/proyectos/asignacion_views.xml',
        'views/admin/operaciones/miembro_views.xml',
        'views/admin/operaciones/registro_views.xml',
        'views/admin/configuracion/etapa_views.xml',
        'views/admin/configuracion/tipo_escaner_views.xml',
        'views/admin/dashboard/dashboard_admin.xml',

        # 4. Menús — siempre después de las acciones
        'views/admin/menus.xml',

        # 5. Portal (vistas QWeb website — Líder)
        'views/portal/portal_home.xml',
        'views/portal/portal_proyecto.xml',
        'views/portal/portal_registro_form.xml',
        'views/portal/portal_miembros.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}