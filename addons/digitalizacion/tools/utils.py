# -*- coding: utf-8 -*-
"""
utils.py — Utilidades puras del módulo de Digitalización
=========================================================

PRINCIPIO DRY: Este archivo centraliza toda la lógica de sanitización
y validación de datos que antes estaba duplicada/mezclada en portal.py.

Al ser funciones puras (sin estado, sin ORM), pueden ser importadas
desde cualquier capa: controllers, models, wizards o tests.

Contenido:
    - sanitizar_entero     → valida y convierte a int dentro de un rango
    - sanitizar_texto      → limpia y valida strings
    - validar_id_positivo  → valida IDs de base de datos
"""

import re

from odoo import _
from odoo.exceptions import ValidationError
from .constantes import (
    MAX_CAMPO_NUMERICO,
    MAX_LEN_TEXTO_CORTO,
    MAX_LEN_TEXTO_LARGO,
)


# ── Sanitización numérica ─────────────────────────────────────────────────────


def sanitizar_entero(valor, nombre_campo, min_val=0, max_val=MAX_CAMPO_NUMERICO):
    """
    Convierte `valor` a int y lo valida dentro de [min_val, max_val].

    Retorna 0 si el valor está vacío/nulo.
    Lanza ValidationError con mensaje amigable si la conversión o el rango falla.

    Uso:
        folios = sanitizar_entero(fila.get("total_folios"), _("Folios totales"))
    """
    if valor is None or valor == "" or valor is False:
        return 0
    try:
        v = int(valor)
    except (TypeError, ValueError):
        raise ValidationError(
            _(
                "El campo '%s' debe ser un número entero, no '%s'.",
                nombre_campo,
                str(valor)[:30],
            )
        )
    if v < min_val:
        raise ValidationError(
            _("El campo '%s' no puede ser negativo (valor: %d).", nombre_campo, v)
        )
    if v > max_val:
        raise ValidationError(
            _(
                "El campo '%s' supera el máximo permitido de %d (valor: %d).",
                nombre_campo,
                max_val,
                v,
            )
        )
    return v


def validar_id_positivo(valor, nombre_campo, prefijo=""):
    """
    Valida que `valor` sea un entero positivo (útil para IDs de BD).

    Retorna el int validado.
    Lanza ValidationError si es nulo, no entero o <= 0.

    Uso:
        miembro_id = validar_id_positivo(fila.get("miembro_id"), "miembro_id", prefijo)
    """
    if not valor:
        raise ValidationError(
            _("%s: falta el campo requerido '%s'.", prefijo, nombre_campo)
        )
    try:
        v = int(valor)
        if v <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError(
            _(
                "%s: '%s' debe ser un ID válido (entero positivo), no '%s'.",
                prefijo,
                nombre_campo,
                valor,
            )
        )
    return v


# ── Sanitización de texto ─────────────────────────────────────────────────────


def sanitizar_texto(valor, nombre_campo, max_len=MAX_LEN_TEXTO_LARGO):
    """
    Limpia y valida `valor` como string.

    - Convierte tipos no-string a string (excepto None/False → devuelve None).
    - Aplica strip().
    - Rechaza si supera max_len.
    - Devuelve None si el resultado está vacío.

    Uso:
        obs = sanitizar_texto(fila.get("observacion"), _("Observación"))
    """
    if valor is None or valor is False:
        return None
    if not isinstance(valor, str):
        valor = str(valor)[:max_len]
    valor = valor.strip()
    if not valor:
        return None
    if len(valor) > max_len:
        raise ValidationError(
            _(
                "El campo '%s' no puede superar %d caracteres (actual: %d).",
                nombre_campo,
                max_len,
                len(valor),
            )
        )
    return valor


def sanitizar_referencia_cajas(valor, prefijo=""):
    """
    Sanitiza el campo 'referencia_cajas' con validación extra:
    rechaza strings compuestos solo de símbolos especiales.

    Retorna el string limpio o None.
    """
    texto = sanitizar_texto(
        valor, _("Referencia de cajas"), max_len=MAX_LEN_TEXTO_CORTO
    )
    if texto and not re.search(r"[\w\d]", texto):
        raise ValidationError(
            _(
                "%s: 'Referencia de cajas' solo contiene símbolos: '%s'.",
                prefijo,
                texto,
            )
        )
    return texto
