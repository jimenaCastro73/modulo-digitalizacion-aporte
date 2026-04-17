# -*- coding: utf-8 -*-
{
    "name": "Gestión de Digitalización",
    "version": "17.0.2.0.0",
    "category": "Services",
    "summary": "Gestión de proyectos de digitalización de documentos",
    "author": "Jimena Castro — Práctica Profesional OTEC GLOBAL",
    "icon_image": "static/description/icon.png",
    "depends": ["base", "contacts", "website"],
    "data": [
        # 1. Seguridad primero: grupos, reglas y ACLs
        "security/digitalizacion_groups.xml",
        "security/digitalizacion_proyecto_security.xml",
        "security/digitalizacion_registro_security.xml",
        "security/ir.model.access.csv",
        # --- Datos ---
        "data/etapa_data.xml",
        # --- Vistas del backoffice ---
        # Vistas de configuración
        "views/admin/configuracion/etapa_views.xml",
        "views/admin/configuracion/tipo_escaner_views.xml",
        # Vistas de apoyo
        "views/admin/proyectos/registro_views.xml",
        # Vistas de proyecto
        "views/admin/proyectos/proyecto_search.xml",
        "views/admin/proyectos/proyecto_views.xml",
        "views/admin/proyectos/proyecto_actions.xml",
        # Dashboard global
        "views/admin/dashboard_views.xml",
        # Menús
        "views/admin/digitalizacion_menus.xml",
        # --- Vistas Portal (Líder) ---
        "views/portal/portal_home_templates.xml",
        "views/portal/portal_proyecto_templates.xml",
        "views/portal/portal_registro_form_templates.xml",
        "views/portal/portal_miembros_templates.xml",
        "views/portal/website_menu.xml",
        # --- Reportes PDF ---
        "report/proyecto_report_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "digitalizacion/static/src/portal/css/portal_digitalizacion.css",
            "digitalizacion/static/src/portal/js/portal_registro_form.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",
}
