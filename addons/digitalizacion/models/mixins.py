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


class _ConteoRegistrosMixin(models.AbstractModel):
    """
    Mixin que proporciona el método `_compute_conteo_desde_registro`
    para contar registros relacionados mediante _read_group.

    Evita repetir el mismo patrón de _read_group + dict de conteos en
    etapa.py y tipo_escaner.py.

    PRINCIPIO DRY: el patrón "si no hay ids, poner 0; si hay, _read_group,
    mapear a dict, recorrer self" estaba duplicado en ambos modelos.
    """

    _name = "digitalizacion.mixin.conteo_registros"
    _description = "Mixin: conteo de registros con _read_group"

    def _compute_conteo_desde_registro(self, campo_agrupacion, campo_destino):
        """
        Cuenta registros en digitalizacion.registro agrupados por
        `campo_agrupacion` y asigna el resultado al campo `campo_destino`
        de cada record del recordset actual.

        Parámetros:
            campo_agrupacion (str): campo en digitalizacion.registro que
                                    apunta a este modelo. Ej: "etapa_id".
            campo_destino    (str): campo Integer en este modelo donde se
                                    guarda el conteo. Ej: "registro_count".
        """
        if not self.ids:
            for record in self:
                setattr(record, campo_destino, 0)
            return

        datos = self.env["digitalizacion.registro"]._read_group(
            domain=[(campo_agrupacion, "in", self.ids)],
            groupby=[campo_agrupacion],
            aggregates=["__count"],
        )
        conteos = {item.id: count for item, count in datos}

        for record in self:
            setattr(record, campo_destino, conteos.get(record.id, 0))
