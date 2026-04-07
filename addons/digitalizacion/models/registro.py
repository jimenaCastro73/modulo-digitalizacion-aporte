# -*- coding: utf-8 -*-
"""
registro.py — Modelo: digitalizacion.registro
Tabla T-06 · Registro diario de trabajo de digitalización

Granularidad:
    1 registro = 1 miembro + 1 etapa + cantidades acumuladas del día.
    El Líder agrega N registros por jornada, uno por cada combinación
    miembro+etapa trabajada ese día.

Campos de caja:
    referencia_cajas (Char) — texto libre. Acepta IDs separados por coma
    ("BF202, BF199, BF208") o descripciones ("7 cajas", "3 cajas aprox.").
    Fiel al proceso real donde las cajas no siempre tienen código asignado.

Orden de etapas (ciclo completo de una caja):
    1. Limpieza  2. Ordenado  3. Digitalizado  4. Editado  5. Indexado

Campos activos por etapa:
    Limpieza / Ordenado → referencia_cajas, no_expedientes, total_folios
    Digitalizado        → referencia_cajas, no_expedientes, total_folios,
                          total_escaneos, tipo_escaner_ids
    Editado             → expedientes_editados, folios_editados
    Indexado            → expedientes_indexados, folios_indexados

Relaciones:
    lider_id         → res.users                       (auditoría)
    miembro_id       → digitalizacion.miembro_proyecto (T-05)
    proyecto_id      → digitalizacion.proyecto         (T-03)
    etapa_id         → digitalizacion.etapa            (T-01)
    tipo_escaner_ids → digitalizacion.tipo_escaner     (T-02, Many2many)
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Límite superior razonable de producción por jornada (evita datos erróneos)
_LIMITE_PRODUCCION_DIARIA = 999_999

# ── Configuración por etapa ───────────────────────────────────────────────────
#
# Cada entrada del diccionario define:
#   "palabras_clave" : lista de fragmentos que pueden aparecer en el nombre de etapa
#   "campos_minimos": lista de campos — al menos uno debe ser > 0
#   "campo_principal": campo que se usa como métrica de producción principal
#   "unidad"        : etiqueta de la unidad para mostrar en reportes
#   "limpiar_al_cambiar": campos que se resetean si la etapa ya no corresponde
#
# Esto centraliza la lógica que antes estaba en 3 if/elif distintos.
# Si se agrega una nueva etapa, solo hay que agregar una entrada aquí.
_CONFIG_POR_ETAPA = {
    "digitalizado": {
        "palabras_clave": ["digitalizado"],
        "campos_minimos": ["total_escaneos", "total_folios"],
        "campo_principal": "total_escaneos",
        "unidad": "escaneos",
        "limpiar_al_cambiar": ["total_escaneos", "tipo_escaner_ids"],
        "mensaje_minimo": "Número de escaneos' o 'Cantidad de folios",
    },
    "editado": {
        "palabras_clave": ["editado"],
        "campos_minimos": ["expedientes_editados", "folios_editados"],
        "campo_principal": "expedientes_editados",
        "unidad": "exp. editados",
        "limpiar_al_cambiar": ["expedientes_editados", "folios_editados"],
        "mensaje_minimo": "Expedientes editados' o 'Folios editados",
    },
    "indexado": {
        "palabras_clave": ["indexado"],
        "campos_minimos": ["expedientes_indexados", "folios_indexados"],
        "campo_principal": "expedientes_indexados",
        "unidad": "exp. indexados",
        "limpiar_al_cambiar": ["expedientes_indexados", "folios_indexados"],
        "mensaje_minimo": "Expedientes indexados' o 'Folios indexados",
    },
    "limpieza_ordenado": {
        "palabras_clave": ["limpieza", "ordenado"],
        "campos_minimos": ["no_expedientes", "total_folios"],
        "campo_principal": "no_expedientes",
        "unidad": "expedientes",
        "limpiar_al_cambiar": [],  # estos campos son comunes a varias etapas
        "mensaje_minimo": "Expedientes' o 'Folios",
    },
}

# Configuración por defecto cuando el nombre de etapa no encaja en ninguna
_CONFIG_ETAPA_DEFAULT = {
    "campo_principal": "total_folios",
    "unidad": "folios",
    "campos_minimos": [],
    "limpiar_al_cambiar": [],
    "mensaje_minimo": "",
}


class Registro(models.Model):
    _name = "digitalizacion.registro"
    _description = "Registro Diario de Trabajo de Digitalización"
    _order = "fecha desc, id desc"
    _rec_name = "display_name"

    # ── Auditoría y relaciones principales ───────────────────────────────────

    lider_id = fields.Many2one(
        comodel_name="res.users",
        string="Registrado por",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
        help="Usuario que realizó el registro. Auto-completado con el usuario en sesión.",
    )

    miembro_id = fields.Many2one(
        comodel_name="digitalizacion.miembro_proyecto",
        string="Digitalizador",
        required=True,
        ondelete="restrict",
        index=True,
        help="Integrante del equipo al que pertenece el trabajo registrado.",
    )

    proyecto_id = fields.Many2one(
        comodel_name="digitalizacion.proyecto",
        string="Proyecto",
        required=True,
        ondelete="restrict",
        index=True,
    )

    etapa_id = fields.Many2one(
        comodel_name="digitalizacion.etapa",
        string="Etapa",
        required=True,
        ondelete="restrict",
        index=True,
        help="Etapa del proceso. Determina qué campos son visibles.",
    )

    # ── Campos temporales ─────────────────────────────────────────────────────

    fecha = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.today,
        index=True,
    )

    hora = fields.Datetime(
        string="Hora de envío",
        default=fields.Datetime.now,
        readonly=True,
        help="Timestamp de cuando se guardó el formulario.",
    )

    # ── Campo común a todas las etapas ────────────────────────────────────────

    observacion = fields.Text(
        string="Observaciones",
        help="Incidencias, notas de la jornada, etc.",
    )

    # ── Campos etapa: Limpieza / Ordenado / Digitalizado ─────────────────────

    referencia_cajas = fields.Char(
        string="Referencia de cajas",
        help="Texto libre. Acepta IDs separados por coma (BF202, BF199) "
        "o descripciones ('7 cajas', '3 cajas aprox.'). "
        "Aplica a: Limpieza, Ordenado, Digitalizado.",
    )

    no_expedientes = fields.Integer(
        string="Cantidad de expedientes",
        help="Total de expedientes físicos procesados en la jornada. "
        "Aplica a: Limpieza, Ordenado.",
    )

    total_folios = fields.Integer(
        string="Cantidad de folios",
        help="Total de folios (hojas físicas) procesados. "
        "Aplica a: Limpieza, Ordenado, Digitalizado.",
    )

    # ── Campos etapa: Digitalizado ────────────────────────────────────────────

    total_escaneos = fields.Integer(
        string="Número de escaneos",
        help="Hojas digitales generadas. Aplica a: Digitalizado.",
    )

    tipo_escaner_ids = fields.Many2many(
        comodel_name="digitalizacion.tipo_escaner",
        string="Tipo(s) de escáner",
        help="Equipo(s) utilizados. Aplica a: Digitalizado.",
    )

    # ── Campos etapa: Editado ─────────────────────────────────────────────────

    expedientes_editados = fields.Integer(
        string="Expedientes editados",
        help="Expedientes que pasaron por edición digital. Aplica a: Editado.",
    )

    folios_editados = fields.Integer(
        string="Folios editados",
        help="Folios editados digitalmente. Aplica a: Editado.",
    )

    # ── Campos etapa: Indexado ────────────────────────────────────────────────

    expedientes_indexados = fields.Integer(
        string="Expedientes indexados",
        help="Expedientes con metadatos asignados. Aplica a: Indexado.",
    )

    folios_indexados = fields.Integer(
        string="Folios indexados",
        help="Folios digitales indexados. Aplica a: Indexado.",
    )

    # ── Campos computados y relacionados ──────────────────────────────────────

    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=False,
    )

    miembro_nombre = fields.Char(
        string="Nombre del digitalizador",
        related="miembro_id.partner_id.name",
        store=True,
        readonly=True,
        index=True,
    )

    proyecto_nombre = fields.Char(
        string="Nombre del proyecto",
        related="proyecto_id.name",
        store=True,
        readonly=True,
    )

    etapa_nombre = fields.Char(
        string="Nombre de la etapa",
        related="etapa_id.name",
        store=True,
        readonly=True,
        index=True,
    )

    lider_nombre = fields.Char(
        string="Nombre del líder",
        related="lider_id.name",
        store=True,
        readonly=True,
    )

    produccion_principal = fields.Integer(
        string="Producción principal",
        compute="_compute_produccion_principal",
        store=True,
        help="Cantidad representativa según etapa.",
    )

    unidad_produccion = fields.Char(
        string="Unidad",
        compute="_compute_produccion_principal",
        store=True,
    )

    # ── Restricciones Python ──────────────────────────────────────────────────

    @api.constrains("miembro_id", "proyecto_id")
    def _check_miembro_pertenece_proyecto(self):
        """
        Verifica que el digitalizador pertenezca al mismo proyecto del registro.

        Regla de negocio: no se puede registrar trabajo de un miembro
        que pertenece a un proyecto distinto al del registro.
        """
        for record in self:
            # Solo validamos si ambos campos tienen valor
            hay_miembro_y_proyecto = record.miembro_id and record.proyecto_id
            if not hay_miembro_y_proyecto:
                continue

            miembro_pertenece_al_proyecto = (
                record.miembro_id.proyecto_id.id == record.proyecto_id.id
            )
            if not miembro_pertenece_al_proyecto:
                raise ValidationError(
                    _(
                        "El digitalizador '%s' no pertenece al proyecto '%s'.",
                        record.miembro_id.partner_id.name,
                        record.proyecto_id.name,
                    )
                )

    @api.constrains("miembro_id")
    def _check_miembro_activo(self):
        """
        Verifica que el digitalizador no tenga fecha de salida registrada.

        Regla de negocio: un miembro que ya salió del equipo no puede
        tener nuevos registros de trabajo.
        """
        for record in self:
            miembro_ya_salio = record.miembro_id and record.miembro_id.fecha_salida
            if miembro_ya_salio:
                raise ValidationError(
                    _(
                        "'%s' tiene fecha de salida (%s). "
                        "No se pueden crear nuevos registros.",
                        record.miembro_id.partner_id.name,
                        record.miembro_id.fecha_salida,
                    )
                )

    @api.constrains("fecha")
    def _check_fecha_no_futura(self):
        """
        La fecha del registro no puede ser futura.

        Regla de negocio: los registros son de trabajo ya realizado,
        no se permite anticipar producción.
        """
        hoy = fields.Date.today()
        for record in self:
            fecha_es_futura = record.fecha and record.fecha > hoy
            if fecha_es_futura:
                raise ValidationError(
                    _(
                        "La fecha (%s) no puede ser futura.",
                        record.fecha,
                    )
                )

    @api.constrains(
        "no_expedientes",
        "total_folios",
        "total_escaneos",
        "expedientes_editados",
        "folios_editados",
        "expedientes_indexados",
        "folios_indexados",
    )
    def _check_valores_positivos(self):
        """
        Valida que todos los campos numéricos de producción estén dentro
        del rango permitido: entre 0 y _LIMITE_PRODUCCION_DIARIA.

        El límite superior existe para detectar errores de tipeo,
        por ejemplo: 9999999 en vez de 99.
        """
        campos_a_validar = [
            ("no_expedientes", _("Cantidad de expedientes")),
            ("total_folios", _("Cantidad de folios")),
            ("total_escaneos", _("Número de escaneos")),
            ("expedientes_editados", _("Expedientes editados")),
            ("folios_editados", _("Folios editados")),
            ("expedientes_indexados", _("Expedientes indexados")),
            ("folios_indexados", _("Folios indexados")),
        ]
        for record in self:
            for nombre_campo, etiqueta in campos_a_validar:
                valor = getattr(record, nombre_campo)
                if valor < 0:
                    raise ValidationError(
                        _("%s no puede ser negativo (valor: %d).", etiqueta, valor)
                    )
                if valor > _LIMITE_PRODUCCION_DIARIA:
                    raise ValidationError(
                        _(
                            "%s supera el límite permitido de %d por jornada (valor: %d). "
                            "Verifica que el dato sea correcto.",
                            etiqueta,
                            _LIMITE_PRODUCCION_DIARIA,
                            valor,
                        )
                    )

    @api.constrains(
        "etapa_id",
        "total_escaneos",
        "expedientes_editados",
        "folios_editados",
        "expedientes_indexados",
        "folios_indexados",
        "no_expedientes",
        "total_folios",
    )
    def _check_campos_minimos_por_etapa(self):
        """
        Valida que al menos un campo de producción esté informado según la etapa.

        Usa el nombre de la etapa (en minúsculas) para identificar la
        configuración, en vez de IDs. Esto hace el código más legible y
        resistente a cambios de base de datos.

        La configuración de cada etapa vive en _CONFIG_POR_ETAPA.
        """
        for record in self:
            if not record.etapa_id:
                continue  # etapa vacía — otra constraint se encargará

            config = self._get_config_etapa(record.etapa_id.name)
            campos_minimos = config.get("campos_minimos", [])

            if not campos_minimos:
                continue  # etapa sin requisitos mínimos definidos

            # Verificar que al menos uno de los campos requeridos tenga valor
            hay_al_menos_un_valor = any(
                getattr(record, campo) for campo in campos_minimos
            )
            if not hay_al_menos_un_valor:
                raise ValidationError(
                    _(
                        "La etapa '%s' requiere '%s'.",
                        record.etapa_id.name,
                        config.get("mensaje_minimo", ""),
                    )
                )

    @api.constrains("referencia_cajas")
    def _check_referencia_cajas(self):
        """
        Si se ingresa referencia de cajas, debe tener contenido útil.

        Acepta texto libre ("BF202, BF199", "7 cajas aprox.") pero
        rechaza strings que solo contengan espacios o símbolos.
        """
        for record in self:
            referencia = record.referencia_cajas

            # Early return: campo vacío es válido (no es obligatorio)
            if not referencia:
                continue

            referencia_limpia = referencia.strip()

            if not referencia_limpia:
                raise ValidationError(
                    _(
                        "'Referencia de cajas' no puede contener solo espacios en blanco."
                    )
                )

            tiene_caracteres_utiles = re.search(r"[\w\d]", referencia_limpia)
            if not tiene_caracteres_utiles:
                raise ValidationError(
                    _(
                        "'Referencia de cajas' debe contener al menos una letra o número "
                        "(valor ingresado: '%s').",
                        referencia_limpia,
                    )
                )

    @api.constrains("observacion")
    def _check_observacion_longitud(self):
        """
        La observación no debe superar los 2000 caracteres.

        Límite definido para evitar entradas excessivamente largas
        en la columna TEXT de PostgreSQL.
        """
        _MAX_CHARS_OBSERVACION = 2000
        for record in self:
            if not record.observacion:
                continue
            longitud_actual = len(record.observacion)
            supera_limite = longitud_actual > _MAX_CHARS_OBSERVACION
            if supera_limite:
                raise ValidationError(
                    _(
                        "Las observaciones no pueden superar %d caracteres "
                        "(actual: %d).",
                        _MAX_CHARS_OBSERVACION,
                        longitud_actual,
                    )
                )

    # ── Métodos computados ────────────────────────────────────────────────────

    @api.depends("lider_id", "miembro_id", "etapa_id", "fecha")
    def _compute_display_name(self):
        """
        Nombre de visualización del registro.
        Formato: «Nombre Digitalizador · Etapa · Fecha»
        """
        for record in self:
            miembro = record.miembro_id.partner_id.name or "?"
            etapa = record.etapa_id.name or "?"
            fecha = str(record.fecha) if record.fecha else "?"
            record.display_name = f"{miembro} · {etapa} · {fecha}"

    @api.depends(
        "etapa_id",
        "etapa_id.name",
        "total_escaneos",
        "no_expedientes",
        "expedientes_editados",
        "expedientes_indexados",
        "folios_editados",
        "folios_indexados",
        "total_folios",
    )
    def _compute_produccion_principal(self):
        """
        Calcula la métrica de producción representativa según la etapa.

        Cada etapa tiene un campo principal diferente:
          - Digitalizado → total_escaneos
          - Editado      → expedientes_editados
          - Indexado     → expedientes_indexados
          - Limpieza / Ordenado → no_expedientes
          - Otros        → total_folios (valor genérico)

        Delega la lógica de qué campo corresponde a _get_config_etapa(),
        así solo hay un lugar donde mantener esas reglas.
        """
        for record in self:
            config = self._get_config_etapa(record.etapa_id.name)
            campo_principal = config["campo_principal"]
            record.produccion_principal = getattr(record, campo_principal) or 0
            record.unidad_produccion = config["unidad"]

    # ── Método extensible: configuración de etapa ─────────────────────────────

    def _get_config_etapa(self, nombre_etapa):
        """
        Retorna la configuración de campos para una etapa dado su nombre.

        Busca en _CONFIG_POR_ETAPA comparando el nombre (en minúsculas)
        con las palabras clave de cada configuración.

        Este método está pensado para ser sobreescrito por módulos que
        necesiten agregar nuevas etapas con sus propias reglas de campos.

        :param nombre_etapa: str, nombre de la etapa (ej: "Digitalizado")
        :return: dict con las claves: campo_principal, unidad,
                 campos_minimos, limpiar_al_cambiar, mensaje_minimo
        """
        nombre_minuscula = (nombre_etapa or "").lower()

        for config in _CONFIG_POR_ETAPA.values():
            for palabra_clave in config["palabras_clave"]:
                if palabra_clave in nombre_minuscula:
                    return config

        # Si el nombre de etapa no coincide con ninguna configuración conocida
        return _CONFIG_ETAPA_DEFAULT

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange("etapa_id")
    def _onchange_etapa(self):
        """
        Limpia los campos que NO corresponden a la etapa seleccionada.

        Cuando el líder cambia la etapa en el formulario, los campos
        de otras etapas se resetean para evitar datos inconsistentes
        (ej: dejar escaneos llenos al cambiar a Editado).

        Usa _get_config_etapa() para saber qué campos limpiar.
        """
        if not self.etapa_id:
            return

        config_actual = self._get_config_etapa(self.etapa_id.name)
        campos_que_usa_esta_etapa = set(config_actual.get("limpiar_al_cambiar", []))

        # Limpiar campos de cada etapa que no sea la actual
        for config in _CONFIG_POR_ETAPA.values():
            for campo in config.get("limpiar_al_cambiar", []):
                if campo not in campos_que_usa_esta_etapa:
                    if campo == "tipo_escaner_ids":
                        setattr(self, campo, [(5, 0, 0)])
                    else:
                        setattr(self, campo, 0)

        # Si la etapa no es de tipo caja, limpiar referencia_cajas y no_expedientes
        etapas_que_usan_cajas = {"limpieza", "ordenado", "digitalizado"}
        etapa_usa_cajas = any(
            palabra in (self.etapa_id.name or "").lower()
            for palabra in etapas_que_usan_cajas
        )
        if not etapa_usa_cajas:
            self.referencia_cajas = False
            self.no_expedientes = 0

    @api.onchange("proyecto_id")
    def _onchange_proyecto_limpiar_miembro(self):
        """
        Al cambiar el proyecto, limpia el digitalizador seleccionado.

        También retorna el dominio actualizado para que el selector de
        miembro solo muestre los que pertenecen al nuevo proyecto y
        no tienen fecha de salida.
        """
        self.miembro_id = False

        if not self.proyecto_id:
            return

        return {
            "domain": {
                "miembro_id": [
                    ("proyecto_id", "=", self.proyecto_id.id),
                    ("active", "=", True),
                    ("fecha_salida", "=", False),
                ]
            }
        }

    # ── Overrides CRUD ────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """
        Fuerza que lider_id y hora sean siempre los del servidor.

        El líder no puede elegir el usuario — siempre se asigna el usuario
        en sesión. Así se garantiza la auditoría de quién hizo el registro.
        """
        usuario_actual = self.env.user.id
        momento_de_creacion = fields.Datetime.now()

        for vals in vals_list:
            vals["lider_id"] = usuario_actual
            if not vals.get("hora"):
                vals["hora"] = momento_de_creacion

        return super().create(vals_list)

    def write(self, vals):
        """
        Impide que lider_id sea modificado después de la creación.

        Si se intenta cambiar lider_id (por ejemplo, desde código externo),
        se ignora silenciosamente y se registra un warning para el admin.
        """
        intento_cambiar_lider = "lider_id" in vals
        if intento_cambiar_lider:
            vals.pop("lider_id")
            _logger.warning(
                "Intento de modificar lider_id en registro(s) %s. Ignorado.",
                self.ids,
            )

        return super().write(vals)

    # ── Métodos de negocio ────────────────────────────────────────────────────

    def action_duplicar_para_hoy(self):
        """
        Duplica este registro cambiando la fecha a hoy.

        Útil cuando el líder quiere registrar el mismo equipo
        y las mismas cantidades que el día anterior.

        :return: action que abre el registro duplicado en modo formulario
        """
        self.ensure_one()
        nuevo_registro = self.copy(
            default={
                "fecha": fields.Date.today(),
                "hora": fields.Datetime.now(),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Registro duplicado"),
            "res_model": "digitalizacion.registro",
            "res_id": nuevo_registro.id,
            "view_mode": "form",
            "target": "current",
        }

    # ── Métodos de consulta para portal y reportes ────────────────────────────

    @api.model
    def get_kpis_lider(self, lider_id, domain_extra=None):
        """
        Calcula los KPIs del dashboard para el líder usando una sola query SQL.

        Usa _read_group con agregaciones para que la suma ocurra
        en PostgreSQL, no en Python (mucho más eficiente).

        :param lider_id: int, ID del usuario líder
        :param domain_extra: lista de tuplas de dominio adicional (filtros de fecha, proyecto)
        :return: dict con claves escaneos, folios_fisicos, exp_indexados, total_registros
        """
        dominio_base = [("lider_id", "=", lider_id)]
        dominio_completo = dominio_base + (domain_extra or [])

        resultados = self.sudo()._read_group(
            domain=dominio_completo,
            groupby=[],
            aggregates=[
                "total_escaneos:sum",
                "total_folios:sum",
                "expedientes_indexados:sum",
                "__count",
            ],
        )

        if resultados:
            escaneos, folios, indexados, total_registros = resultados[0]
        else:
            escaneos, folios, indexados, total_registros = 0, 0, 0, 0

        return {
            "escaneos": escaneos or 0,
            "folios_fisicos": folios or 0,
            "exp_indexados": indexados or 0,
            "total_registros": total_registros,
        }

    @api.model
    def get_resumen_por_etapa(self, proyecto_id):
        """
        Resumen de producción agrupada por etapa para un proyecto.

        Utilizado en el dashboard del backend para mostrar cuánto
        se ha producido en cada etapa del proceso.

        :param proyecto_id: int, ID del proyecto
        :return: lista de dicts [{"etapa": str, "total": int, "unidad": str}, ...]
        """
        registros_del_proyecto = self.sudo().search([("proyecto_id", "=", proyecto_id)])
        resumen_por_etapa = {}

        for registro in registros_del_proyecto:
            nombre_etapa = registro.etapa_id.name or "Sin etapa"

            if nombre_etapa not in resumen_por_etapa:
                resumen_por_etapa[nombre_etapa] = {
                    "etapa": nombre_etapa,
                    "total": 0,
                    "unidad": registro.unidad_produccion,
                }
            resumen_por_etapa[nombre_etapa]["total"] += (
                registro.produccion_principal or 0
            )

        return sorted(
            resumen_por_etapa.values(),
            key=lambda resumen_etapa: resumen_etapa["etapa"],
        )

    @api.model
    def get_participacion_equipo(self, proyecto_id):
        """
        Participación de cada miembro por etapa para un proyecto.
        Usado en la vista de miembros del portal: gráfico de barras apiladas
        + tabla heatmap. Una sola query agrupada, sin N+1.

        Retorna:
        {
            "etapas": ["Limpieza", "Ordenado", ...],   # en orden de sequence
            "miembros": [
                {
                    "nombre": "María López",
                    "total": 20,
                    "por_etapa": {"Limpieza": 4, "Digitalizado": 7, ...},
                    "segmentos": [                      # para barras apiladas
                        {"etapa": "Limpieza", "count": 4, "pct": 20},
                        {"etapa": "Digitalizado", "count": 7, "pct": 35},
                        ...
                    ],
                },
                ...
            ],
        }
        """
        # Una sola query agrupada por miembro y etapa (evita N+1 queries)
        datos = self.sudo()._read_group(
            domain=[("proyecto_id", "=", proyecto_id)],
            groupby=["miembro_id", "etapa_id"],
            aggregates=["__count"],
        )

        # Etapas en orden de sequence (para columnas y leyenda)
        etapas_en_orden = (
            self.env["digitalizacion.etapa"]
            .sudo()
            .search([("active", "=", True)], order="sequence asc")
            .mapped("name")
        )

        # Construir mapa { miembro_id: { etapa_nombre: cantidad } }
        participacion_por_miembro = {}
        for miembro, etapa, cantidad in datos:
            miembro_key = miembro.id
            if miembro_key not in participacion_por_miembro:
                participacion_por_miembro[miembro_key] = {
                    "nombre": miembro.partner_id.name or miembro.display_name,
                    "por_etapa": {},
                    "total": 0,
                }
            nombre_etapa = etapa.name or "Sin etapa"
            participacion_por_miembro[miembro_key]["por_etapa"][nombre_etapa] = cantidad
            participacion_por_miembro[miembro_key]["total"] += cantidad

        # Ordenar de mayor a menor participación total
        miembros_ordenados = sorted(
            participacion_por_miembro.values(),
            key=lambda datos_miembro: datos_miembro["total"],
            reverse=True,
        )

        # Agregar segmentos para las barras apiladas en QWeb
        for datos_miembro in miembros_ordenados:
            # Evitar división por cero si el total fuera 0
            total_para_porcentaje = datos_miembro["total"] or 1
            datos_miembro["segmentos"] = [
                {
                    "etapa": nombre_etapa,
                    "count": datos_miembro["por_etapa"].get(nombre_etapa, 0),
                    "pct": round(
                        (
                            datos_miembro["por_etapa"].get(nombre_etapa, 0)
                            / total_para_porcentaje
                        )
                        * 100
                    ),
                }
                for nombre_etapa in etapas_en_orden
                if datos_miembro["por_etapa"].get(nombre_etapa, 0) > 0
            ]

        return {
            "etapas": etapas_en_orden,
            "miembros": miembros_ordenados,
        }
