# -*- coding: utf-8 -*-
"""
models/mixins.py — Mixins reutilizables del módulo de Digitalización
"""

import re

from odoo import _, api, models
from odoo.exceptions import ValidationError


class _NombreValidoMixin(models.AbstractModel):
    """
    Mixin que valida que el campo `name` no esté vacío, no sea solo
    numérico y no contenga únicamente caracteres especiales.

    Aplica el mismo criterio a etapa.py, tipo_escaner.py y proyecto.py,
    que tenían esta validación repetida en tres lugares distintos.

    PRINCIPIO KISS: un solo método, una sola regla, cero duplicados.
    """

    _name = "digitalizacion.mixin.nombre_valido"
    _description = "Mixin: validación de nombre"

    # Patrón de caracteres inválidos (solo símbolos, sin letras ni números)
    _PATRON_SOLO_SIMBOLOS = re.compile(r"^[^\w\s\-\.áéíóúÁÉÍÓÚüÜñÑ]+$")

    @api.constrains("name")
    def _check_name(self):
        """
        Valida el campo `name`:
          1. No puede estar vacío.
          2. No puede ser solo dígitos.
          3. No puede ser solo caracteres especiales.

        Se sobreescribe `_nombre_objeto` en cada modelo hijo para
        personalizar los mensajes de error sin duplicar la lógica.
        """
        nombre_objeto = getattr(self, "_nombre_objeto", _("registro"))
        for record in self:
            nombre = (record.name or "").strip()
            if not nombre:
                raise ValidationError(
                    _("El nombre de %s no puede estar vacío.", nombre_objeto)
                )
            if nombre.isdigit():
                raise ValidationError(
                    _(
                        "El nombre de %s no puede ser solo números: '%s'.",
                        nombre_objeto,
                        nombre,
                    )
                )
            if self._PATRON_SOLO_SIMBOLOS.fullmatch(nombre):
                raise ValidationError(
                    _(
                        "El nombre de %s contiene solo caracteres especiales: '%s'.",
                        nombre_objeto,
                        nombre,
                    )
                )