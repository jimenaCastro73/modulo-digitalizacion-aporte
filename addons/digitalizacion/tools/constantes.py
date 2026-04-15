# -*- coding: utf-8 -*-
"""
tools/constantes.py — Constantes globales del módulo de Digitalización

PRINCIPIO DRY: Centraliza todos los valores "quemados" (hardcoded) que antes
estaban dispersos en portal.py y registro.py.

Al importar desde aquí se garantiza que cambiar un límite se propague
automáticamente a todos los archivos que lo usan.

Uso:
    from odoo.addons.digitalizacion.tools.constantes import (
        MAX_FILAS,
        MAX_CAMPO_NUMERICO,
        ETAPAS_CONFIG,
    )
"""

# ── Límites del controlador HTTP ──────────────────────────────────────────────

# Máximo de notificaciones almacenadas en sesión (evita crecimiento ilimitado)
MAX_NOTIFICACIONES = 5

# Máximo de filas por payload JSON (protege contra abuso/DoS)
MAX_FILAS = 50

# Límite numérico razonable por campo de producción
MAX_CAMPO_NUMERICO = 999_999

# Longitud máxima para campos de texto corto (referencia_cajas)
MAX_LEN_TEXTO_CORTO = 200

# Longitud máxima para campos de texto largo (observacion, description)
MAX_LEN_TEXTO_LARGO = 500

# Longitud máxima para descriptions de proyectos
MAX_LEN_DESCRIPCION_PROYECTO = 500

# ── Configuración de etapas ───────────────────────────────────────────────────
# Cada entrada define el comportamiento de una etapa en el modelo registro.py.
#
# Claves:
#   campo_principal   → campo que representa la "producción principal" de la etapa
#   unidad            → etiqueta de la unidad de medida para reportes y KPIs
#   campos_minimos    → lista de campos que DEBEN tener valor > 0 para ser válidos
#   limpiar_al_cambiar→ campos a poner en 0 cuando la etapa cambia
#   mensaje_minimo    → mensaje de error si no se cumple campos_minimos
#
# PRINCIPIO DRY: la lógica de _compute_produccion_principal y _check_campos_etapa
# en registro.py itera sobre este dict en lugar de tener un bloque if/elif por etapa.

ETAPAS_CONFIG = {
    "Limpieza": {
        "campo_principal": "no_expedientes",
        "unidad": "expedientes",
        "campos_minimos": ["no_expedientes", "total_folios"],
        "limpiar_al_cambiar": [
            "total_escaneos",
            "expedientes_editados",
            "folios_editados",
            "expedientes_indexados",
            "folios_indexados",
        ],
        "mensaje_minimo": "En Limpieza debes registrar expedientes o folios.",
    },
    "Ordenado": {
        "campo_principal": "no_expedientes",
        "unidad": "expedientes",
        "campos_minimos": ["no_expedientes", "total_folios"],
        "limpiar_al_cambiar": [
            "total_escaneos",
            "expedientes_editados",
            "folios_editados",
            "expedientes_indexados",
            "folios_indexados",
        ],
        "mensaje_minimo": "En Ordenado debes registrar expedientes o folios.",
    },
    "Digitalizado": {
        "campo_principal": "total_escaneos",
        "unidad": "escaneos",
        "campos_minimos": ["total_escaneos"],
        "limpiar_al_cambiar": [
            "no_expedientes",
            "expedientes_editados",
            "folios_editados",
            "expedientes_indexados",
            "folios_indexados",
        ],
        "mensaje_minimo": "En Digitalizado debes registrar al menos un escaneo.",
    },
    "Editado": {
        "campo_principal": "folios_editados",
        "unidad": "folios",
        "campos_minimos": ["expedientes_editados", "folios_editados"],
        "limpiar_al_cambiar": [
            "no_expedientes",
            "total_escaneos",
            "expedientes_indexados",
            "folios_indexados",
        ],
        "mensaje_minimo": "En Editado debes registrar expedientes o folios editados.",
    },
    "Indexado": {
        "campo_principal": "folios_indexados",
        "unidad": "folios",
        "campos_minimos": ["expedientes_indexados", "folios_indexados"],
        "limpiar_al_cambiar": [
            "no_expedientes",
            "total_escaneos",
            "expedientes_editados",
            "folios_editados",
        ],
        "mensaje_minimo": "En Indexado debes registrar expedientes o folios indexados.",
    },
}

# Configuración por defecto cuando la etapa no está en ETAPAS_CONFIG
ETAPA_DEFAULT_CONFIG = {
    "campo_principal": "total_folios",
    "unidad": "folios",
    "campos_minimos": [],
    "limpiar_al_cambiar": [],
    "mensaje_minimo": "",
}
