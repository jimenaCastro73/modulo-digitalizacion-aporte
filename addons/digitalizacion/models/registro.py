# -*- coding: utf-8 -*-
"""
registro.py — Modelo: digitalizacion.registro
Tabla T-06 · Registro diario de trabajo de digitalización

Tabla principal y transaccional del módulo. Almacena cada unidad de trabajo
registrada por el Líder al final de la jornada.

Granularidad:
  1 registro = 1 miembro + 1 etapa + cantidades acumuladas del día.
  El Líder agrega N registros por jornada, uno por cada combinación
  miembro+etapa trabajada. Un mismo miembro puede tener múltiples registros
  en el mismo día si trabajó en varias etapas.

Estrategia de tabla plana con campos opcionales por etapa:
  Los campos que no corresponden a la etapa activa quedan en NULL.
  La visibilidad dinámica se controla en la vista QWeb del portal (WF-03)
  y en la vista de formulario del backend mediante attrs/invisible.

Relaciones:
  lider_id         → res.users                          (auditoría, auto env.user)
  miembro_id       → digitalizacion.miembro_proyecto    (T-05, digitalizador)
  proyecto_id      → digitalizacion.proyecto            (T-03)
  etapa_id         → digitalizacion.etapa               (T-01)
  tipo_escaner_ids → digitalizacion.tipo_escaner        (T-02, Many2many)
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Registro(models.Model):
    _name        = "digitalizacion.registro"
    _description = "Registro Diario de Trabajo de Digitalización"
    _order       = "fecha desc, id desc"
    _rec_name    = "display_name"

    # =========================================================================
    # CAMPOS DE AUDITORÍA Y RELACIONES PRINCIPALES
    # =========================================================================

    lider_id = fields.Many2one(
        comodel_name = "res.users",
        string       = "Registrado por (Líder)",
        required     = True,
        ondelete     = "restrict",
        default      = lambda self: self.env.user,
        readonly     = True,
        index        = True,
        help         = "Usuario Odoo que realizó el registro. Auto-completado con "
                       "el usuario en sesión. No editable.",
    )

    miembro_id = fields.Many2one(
        comodel_name = "digitalizacion.miembro_proyecto",
        string       = "Digitalizador",
        required     = True,
        ondelete     = "restrict",
        index        = True,
        help         = "Integrante del equipo al que pertenece el trabajo registrado. "
                       "Filtrado por proyecto_id y miembros activos sin fecha_salida.",
    )

    proyecto_id = fields.Many2one(
        comodel_name = "digitalizacion.proyecto",
        string       = "Proyecto",
        required     = True,
        ondelete     = "restrict",
        index        = True,
        help         = "Proyecto al que pertenece el registro. Solo muestra proyectos "
                       "con asignación activa del líder en sesión.",
    )

    etapa_id = fields.Many2one(
        comodel_name = "digitalizacion.etapa",
        string       = "Etapa",
        required     = True,
        ondelete     = "restrict",
        index        = True,
        help         = "Etapa del proceso de digitalización. Determina qué campos "
                       "de detalle son visibles y cuáles quedan en NULL.",
    )

    # =========================================================================
    # CAMPOS TEMPORALES
    # =========================================================================

    fecha = fields.Date(
        string   = "Fecha",
        required = True,
        default  = fields.Date.today,
        index    = True,
        help     = "Fecha de la jornada registrada. Default: hoy.",
    )

    hora = fields.Datetime(
        string  = "Hora de envío",
        default = fields.Datetime.now,
        readonly = True,
        help    = "Timestamp de cuando se guardó el formulario. "
                  "Capturado automáticamente.",
    )

    # =========================================================================
    # CAMPO COMÚN A TODAS LAS ETAPAS
    # =========================================================================

    observacion = fields.Text(
        string = "Observaciones",
        help   = "Campo libre de texto. Incidencias, notas de la jornada, "
                 "atascos de escáner, incorporaciones tardías, etc.",
    )

    # =========================================================================
    # CAMPOS ETAPA: LIMPIEZA / ORDENADO
    # Aplican a: Limpieza, Ordenado
    # =========================================================================

    no_caja = fields.Char(
        string = "Nombre / ID de caja",
        help   = "ETAPAS: Limpieza, Ordenado. "
                 "Identificador o descripción de la caja/folder físico procesado. "
                 "Acepta texto libre (puede listar múltiples cajas separadas por coma, "
                 "igual que el Excel origen). Ej: '504A, 504B, 504C'.",
    )

    cantidad_cajas = fields.Integer(
        string = "Cantidad de cajas",
        help   = "ETAPAS: Limpieza, Ordenado. "
                 "Número de cajas físicas procesadas en esta jornada.",
    )

    no_expedientes = fields.Integer(
        string = "Cantidad de expedientes",
        help   = "ETAPAS: Limpieza, Ordenado. "
                 "Número de expedientes físicos procesados.",
    )

    total_folios = fields.Integer(
        string = "Cantidad de folios",
        help   = "ETAPAS: Limpieza, Ordenado, Digitalizado. "
                 "Número de folios (hojas físicas) procesados. "
                 "El folio es la unidad física individual numerada secuencialmente.",
    )

    # =========================================================================
    # CAMPOS ETAPA: DIGITALIZADO
    # Aplican a: Digitalizado
    # =========================================================================

    total_escaneos = fields.Integer(
        string = "Número de escaneos",
        help   = "ETAPA: Digitalizado. "
                 "Número de hojas digitales generadas (scans). "
                 "Puede diferir de total_folios si hubo re-escaneos o caras dobles.",
    )

    tipo_escaner_id = fields.Many2one(
        comodel_name = "digitalizacion.tipo_escaner",
        string       = "Tipo de escáner",
        help         = "ETAPA: Digitalizado. Equipo utilizado en la sesión.",
    )

    # =========================================================================
    # CAMPOS ETAPA: EDITADO
    # =========================================================================

    expedientes_editados = fields.Integer(
        string = "Expedientes editados",
        help   = "ETAPA: Editado. "
                 "Número de expedientes que pasaron por el proceso de edición digital.",
    )

    folios_editados = fields.Integer(
        string = "Folios editados",
        help   = "ETAPA: Editado. "
                 "Número de folios editados digitalmente.",
    )

    # =========================================================================
    # CAMPOS ETAPA: INDEXADO
    # =========================================================================

    expedientes_indexados = fields.Integer(
        string = "Expedientes indexados",
        help   = "ETAPA: Indexado. "
                 "Número de expedientes a los que se asignaron metadatos/etiquetas.",
    )

    folios_indexados = fields.Integer(
        string = "Folios indexados",
        help   = "ETAPA: Indexado. "
                 "Número de folios digitales indexados.",
    )

    # =========================================================================
    # CAMPOS COMPUTADOS Y RELACIONADOS
    # =========================================================================

    display_name = fields.Char(
        string  = "Nombre",
        compute = "_compute_display_name",
        store   = False,
    )

    # Campos relacionados para lectura rápida en vistas y reportes
    miembro_nombre = fields.Char(
        string   = "Nombre del digitalizador",
        related  = "miembro_id.partner_id.name",
        store    = True,
        readonly = True,
        index    = True,
    )

    proyecto_nombre = fields.Char(
        string   = "Nombre del proyecto",
        related  = "proyecto_id.name",
        store    = True,
        readonly = True,
    )

    etapa_nombre = fields.Char(
        string   = "Nombre de la etapa",
        related  = "etapa_id.name",
        store    = True,
        readonly = True,
        index    = True,
    )

    lider_nombre = fields.Char(
        string   = "Nombre del líder",
        related  = "lider_id.name",
        store    = True,
        readonly = True,
    )

    # Campo resumen: unidad principal de producción según la etapa
    produccion_principal = fields.Integer(
        string  = "Producción principal",
        compute = "_compute_produccion_principal",
        store   = True,
        help    = "Cantidad representativa de la etapa: escaneos para Digitalizado, "
                  "expedientes para Limpieza/Ordenado, folios para Editado/Indexado.",
    )

    unidad_produccion = fields.Char(
        string  = "Unidad",
        compute = "_compute_produccion_principal",
        store   = True,
        help    = "Etiqueta de la unidad de producción principal. "
                  "Ej: 'escaneos', 'expedientes', 'folios edit.'",
    )

    # =========================================================================
    # DOMINIOS DINÁMICOS (definidos como campos compute para el portal)
    # =========================================================================
    # Nota: en vistas de backend Odoo 17, los domains dinámicos se declaran
    # directamente en el XML con domain="[...]" usando uid.
    # Para el portal (QWeb), la lógica de filtrado se resuelve en el controlador.

    # =========================================================================
    # RESTRICCIONES SQL
    # =========================================================================

    # No se agrega UNIQUE en (lider_id, miembro_id, etapa_id, fecha) porque
    # la granularidad del negocio permite múltiples registros del mismo miembro
    # en la misma etapa y fecha (ej: dos tandas de escaneo separadas).
    # El control de duplicados es responsabilidad del Líder.

    # =========================================================================
    # RESTRICCIONES PYTHON
    # =========================================================================

    @api.constrains("miembro_id", "proyecto_id")
    def _check_miembro_pertenece_proyecto(self):
        """
        Verifica que el miembro_id pertenezca al proyecto_id del registro.
        Evita registros huérfanos o con combinaciones inválidas.
        """
        for rec in self:
            if rec.miembro_id and rec.proyecto_id:
                if rec.miembro_id.proyecto_id.id != rec.proyecto_id.id:
                    raise ValidationError(
                        f"El digitalizador '{rec.miembro_id.partner_id.name}' "
                        f"no pertenece al proyecto '{rec.proyecto_id.name}'. "
                        f"Verifica la asignación de miembros."
                    )

    @api.constrains("miembro_id")
    def _check_miembro_activo(self):
        """
        Verifica que el miembro no tenga fecha_salida al momento de registrar.
        Un miembro que ya salió del proyecto no debería recibir nuevos registros.
        """
        for rec in self:
            if rec.miembro_id and rec.miembro_id.fecha_salida:
                raise ValidationError(
                    f"'{rec.miembro_id.partner_id.name}' tiene fecha de salida "
                    f"registrada ({rec.miembro_id.fecha_salida}). "
                    f"No se pueden crear nuevos registros para este miembro."
                )

    @api.constrains("fecha")
    def _check_fecha_no_futura(self):
        """
        El registro no puede ser de una fecha futura.
        El Líder registra al final del día, nunca a futuro.
        """
        hoy = fields.Date.today()
        for rec in self:
            if rec.fecha and rec.fecha > hoy:
                raise ValidationError(
                    f"La fecha del registro ({rec.fecha}) no puede ser futura. "
                    f"El registro debe corresponder a una jornada ya trabajada."
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
        Valida que al menos un campo numérico de producción esté informado
        según la etapa seleccionada. Evita registros vacíos sin datos de producción.

        La validación se basa en etapa_id.name (flexible, sin hardcodear IDs).
        """
        for rec in self:
            if not rec.etapa_id:
                continue

            nombre_etapa = (rec.etapa_id.name or "").lower()

            # Digitalizado: obligatorio al menos num_escaneos o total_folios
            if "digitalizado" in nombre_etapa:
                if not (rec.total_escaneos or rec.total_folios):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere informar al menos "
                        f"'Número de escaneos' o 'Cantidad de folios'."
                    )

            # Editado: obligatorio al menos expedientes o folios editados
            elif "editado" in nombre_etapa:
                if not (rec.expedientes_editados or rec.folios_editados):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere informar al menos "
                        f"'Expedientes editados' o 'Folios editados'."
                    )

            # Indexado: obligatorio al menos expedientes o folios indexados
            elif "indexado" in nombre_etapa:
                if not (rec.expedientes_indexados or rec.folios_indexados):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere informar al menos "
                        f"'Expedientes indexados' o 'Folios indexados'."
                    )

            # Limpieza / Ordenado: al menos expedientes o folios
            elif "limpieza" in nombre_etapa or "ordenado" in nombre_etapa:
                if not (rec.no_expedientes or rec.total_folios or rec.cantidad_cajas):
                    raise ValidationError(
                        f"La etapa '{rec.etapa_id.name}' requiere informar al menos "
                        f"'Cantidad de expedientes', 'Folios' o 'Cajas'."
                    )

    # =========================================================================
    # MÉTODOS COMPUTADOS
    # =========================================================================

    @api.depends("lider_id", "miembro_id", "etapa_id", "fecha")
    def _compute_display_name(self):
        for rec in self:
            miembro = rec.miembro_id.partner_id.name or "?"
            etapa   = rec.etapa_id.name              or "?"
            fecha   = str(rec.fecha)                 if rec.fecha else "?"
            rec.display_name = f"{miembro} · {etapa} · {fecha}"

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
        Determina la cantidad y unidad de producción representativa según la etapa.
        Almacenado (store=True) para filtros y reportes eficientes.

        Mapeo etapa → (campo, etiqueta):
          Digitalizado → num_escaneos         → 'escaneos'
          Editado      → expedientes_editados → 'exp. editados'
          Indexado     → expedientes_indexados → 'exp. indexados'
          Limpieza     → no_expedientes → 'expedientes'
          Ordenado     → no_expedientes → 'expedientes'
          (fallback)   → total_folios      → 'folios'
        """
        for rec in self:
            nombre = (rec.etapa_id.name or "").lower()

            if "digitalizado" in nombre:
                rec.produccion_principal = rec.total_escaneos or 0
                rec.unidad_produccion    = "escaneos"

            elif "editado" in nombre:
                rec.produccion_principal = rec.expedientes_editados or 0
                rec.unidad_produccion    = "exp. editados"

            elif "indexado" in nombre:
                rec.produccion_principal = rec.expedientes_indexados or 0
                rec.unidad_produccion    = "exp. indexados"

            elif "limpieza" in nombre or "ordenado" in nombre:
                rec.produccion_principal = rec.no_expedientes or 0
                rec.unidad_produccion    = "expedientes"

            else:
                rec.produccion_principal = rec.total_folios or 0
                rec.unidad_produccion    = "folios"

    # =========================================================================
    # ONCHANGE — Limpiar campos de otras etapas al cambiar etapa
    # =========================================================================

    @api.onchange("etapa_id")
    def _onchange_etapa(self):
        """Ajusta los campos visibles según la etapa seleccionada."""
        if self.etapa_id:
            nombre = (self.etapa_id.name or "").lower()

            # Limpiar campos de Digitalizado
            if "digitalizado" not in nombre:
                self.total_escaneos = 0
                self.tipo_escaner_id = False

        # Limpiar campos de Editado
        if "editado" not in nombre:
            self.expedientes_editados = 0
            self.folios_editados      = 0

        # Limpiar campos de Indexado
        if "indexado" not in nombre:
            self.expedientes_indexados = 0
            self.folios_indexados      = 0

        # Limpiar campos de Limpieza / Ordenado
        if "limpieza" not in nombre and "ordenado" not in nombre:
            self.cantidad_cajas        = 0
            self.no_expedientes  = 0

    @api.onchange("proyecto_id")
    def _onchange_proyecto_limpiar_miembro(self):
        """
        Al cambiar el proyecto, limpia miembro_id para forzar al usuario
        a seleccionar un miembro válido del nuevo proyecto.
        También retorna el domain dinámico actualizado.
        """
        self.miembro_id = False
        if self.proyecto_id:
            return {
                "domain": {
                    "miembro_id": [
                        ("proyecto_id", "=", self.proyecto_id.id),
                        ("active",      "=", True),
                        ("fecha_salida", "=", False),
                    ]
                }
            }

    # =========================================================================
    # OVERRIDE CREATE / WRITE — Completar lider_id y hora automáticamente
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """
        Asegura que lider_id y hora queden siempre completados con el usuario
        y timestamp actuales, independientemente de lo que envíe el cliente.
        """
        lider_id = self.env.user.id
        ahora    = fields.Datetime.now()

        for vals in vals_list:
            # lider_id: siempre el usuario en sesión, no editable desde cliente
            vals["lider_id"] = lider_id
            # hora: timestamp del momento exacto de creación
            if not vals.get("hora"):
                vals["hora"] = ahora

        return super().create(vals_list)

    def write(self, vals):
        """
        Impide que lider_id sea modificado después de la creación.
        """
        if "lider_id" in vals:
            vals.pop("lider_id")
            _logger.warning(
                "Intento de modificar lider_id en registro(s) %s. Ignorado.",
                self.ids,
            )
        return super().write(vals)

    # =========================================================================
    # MÉTODOS DE NEGOCIO Y ACCIONES
    # =========================================================================

    def action_duplicar_para_hoy(self):
        """
        Duplica el registro cambiando la fecha a hoy.
        Útil cuando el líder quiere reutilizar la estructura de un registro anterior.
        """
        self.ensure_one()
        nuevo = self.copy(default={
            "fecha": fields.Date.today(),
            "hora":  fields.Datetime.now(),
        })
        return {
            "type":      "ir.actions.act_window",
            "name":      "Registro duplicado",
            "res_model": "digitalizacion.registro",
            "res_id":    nuevo.id,
            "view_mode": "form",
        }

    # =========================================================================
    # MÉTODOS DE CONSULTA PARA EL PORTAL Y REPORTES
    # =========================================================================

    @api.model
    def get_kpis_lider(self, lider_id: int, domain_extra: list = None) -> dict:
        """
        Calcula los KPIs del dashboard para el líder indicado.
        Método centralizado, usado desde el controlador y potencialmente
        desde reportes del backend.

        Retorna:
          {
            "escaneos":        int,
            "folios_fisicos":  int,
            "exp_indexados":   int,
            "total_registros": int,
          }
        """
        domain = [("lider_id", "=", lider_id)]
        if domain_extra:
            domain += domain_extra

        registros = self.sudo().search(domain)

        return {
            "escaneos":        sum(r.total_escaneos or 0            for r in registros),
            "folios_fisicos":  sum(r.total_folios or 0         for r in registros),
            "exp_indexados":   sum(r.expedientes_indexados or 0   for r in registros),
            "total_registros": len(registros),
        }

    @api.model
    def get_resumen_por_etapa(self, proyecto_id: int) -> list:
        """
        Resumen de producción agrupado por etapa para un proyecto.
        Usado en el dashboard del backend (Administrador).

        Retorna lista de dicts:
          [{"etapa": "Digitalizado", "total": 1840, "unidad": "escaneos"}, ...]
        """
        registros = self.sudo().search([("proyecto_id", "=", proyecto_id)])
        resumen   = {}

        for rec in registros:
            etapa = rec.etapa_id.name or "Sin etapa"
            if etapa not in resumen:
                resumen[etapa] = {"etapa": etapa, "total": 0, "unidad": rec.unidad_produccion}
            resumen[etapa]["total"] += rec.produccion_principal or 0

        return sorted(resumen.values(), key=lambda x: x["etapa"])