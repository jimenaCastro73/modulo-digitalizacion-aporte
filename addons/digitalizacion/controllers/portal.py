# -*- coding: utf-8 -*-
"""
controllers.py — Módulo de Gestión de Digitalización
Sistema desarrollado en Odoo 17 para OTEC GLOBAL

Rutas del portal (todas bajo /digitalizacion):
    GET  /digitalizacion                          → Dashboard del Líder
    GET  /digitalizacion/registro/<int:proyecto_id> → Formulario multi-fila
    POST /digitalizacion/api/guardar_registros    → Guardado masivo de registros
    POST /digitalizacion/api/buscar_partner       → Búsqueda de contactos (res.partner)
    POST /digitalizacion/api/agregar_miembro      → Vincula partner al proyecto (T-05)

    Convenciones:
        - Solo los usuarios del grupo "Digitalización / Líder" pueden acceder.
        - Todos los endpoints JSON-RPC devuelven {"result": {...}} o {"error": {...}}.
        - El lider_id siempre se resuelve desde request.env.user (nunca desde el cliente).
        """

import json
import logging
from datetime import date

from odoo import fields, http
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _json_response(data: dict, status: int = 200):
    """Devuelve una respuesta JSON con la estructura estándar Odoo JSON-RPC."""
    return request.make_response(
json.dumps({"jsonrpc": "2.0", "id": None, "result": data}),
headers=[("Content-Type", "application/json")],
status=status,
)


def _json_error(message: str, code: int = 200):
    """Devuelve un error en formato JSON-RPC (result con status=error)."""
    return request.make_response(
json.dumps(
    {
        "jsonrpc": "2.0",
        "id": None,
        "result": {"status": "error", "message": message},
    }
),
headers=[("Content-Type", "application/json")],
status=code,
)


def _verificar_lider():
    """
    Verifica que el usuario en sesión pertenezca al grupo de Líderes.
    Lanza AccessError si no tiene permisos.
    El grupo XML ID debe coincidir con el definido en security/ir.model.access.csv.
    """
    if not request.env.user.has_group("digitalizacion.group_digitalizacion_lider"):
        raise AccessError(
    "No tienes permisos para acceder al módulo de digitalización."
)


def _get_asignaciones_activas(lider_id: int):
    """
    Retorna el recordset de asignaciones activas del líder.
    Una asignación activa implica que el proyecto también debe estar activo.
    """
    Asignacion = request.env["digitalizacion.asignacion"].sudo()
    return Asignacion.search(
[
    ("lider_id", "=", lider_id),
    ("active", "=", True),
    ("proyecto_id.active", "=", True),
    ("proyecto_id.state", "=", "activo"),
]
)


def _get_proyecto_del_lider(proyecto_id: int, lider_id: int):
    """
    Verifica que el proyecto pertenezca al líder activo.
    Retorna el record del proyecto o None.
    """
    asig = (
        request.env["digitalizacion.asignacion"]
        .sudo()
        .search(
            [
                ("lider_id", "=", lider_id),
                ("proyecto_id", "=", proyecto_id),
                ("active", "=", True),
                ("proyecto_id.active", "=", True),
                ("proyecto_id.state", "=", "activo"),
            ],
            limit=1,
        )
    )
    return asig.proyecto_id if asig else None


def _calcular_kpis(lider_id: int, domain_extra: list = None) -> dict:
    """
    Delega el cálculo de KPIs al método del modelo para evitar duplicación.
    """
    Registro = request.env["digitalizacion.registro"].sudo()
    return Registro.get_kpis_lider(lider_id, domain_extra=domain_extra)


# ---------------------------------------------------------------------------
# Controlador principal del portal
# ---------------------------------------------------------------------------


class DigitalizacionPortalController(http.Controller):
    # =========================================================================
    # DASHBOARD DEL LÍDER
    # GET /digitalizacion
    # =========================================================================

    @http.route(
        "/digitalizacion",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def dashboard(self, **kwargs):
        """
        Dashboard principal del Líder.

        Parámetros GET opcionales:
            proyecto_id  → int   Filtrar por proyecto específico
            periodo      → str   'hoy' | 'semana' | 'mes' (default) | 'custom'
            fecha_desde  → str   YYYY-MM-DD  (solo si periodo='custom')
            fecha_hasta  → str   YYYY-MM-DD  (solo si periodo='custom')

            Variables renderizadas:
                kpis               → dict
                ultimos_registros  → recordset (10 más recientes)
                asignaciones       → recordset de digitalizacion.asignacion
                miembros_equipo    → recordset de digitalizacion.miembro_proyecto
                periodo_actual     → str descripción legible del período
                """
                try:
                    _verificar_lider()
                except AccessError:
                    return request.redirect("/web/login")

                lider = request.env.user
                lider_id = lider.id

                # ── Parámetros de filtro ─────────────────────────────────────────────
                proyecto_id_raw = kwargs.get("proyecto_id", "")
                periodo = kwargs.get("periodo", "mes")
                fecha_desde_raw = kwargs.get("fecha_desde", "")
                fecha_hasta_raw = kwargs.get("fecha_hasta", "")

                # ── Resolver fechas del período ──────────────────────────────────────
                hoy = date.today()
                domain_fecha = []
                periodo_actual = ""

                if periodo == "hoy":
                    domain_fecha = [("fecha", "=", hoy)]
                    periodo_actual = f"Hoy · {hoy.strftime('%d/%m/%Y')}"

                elif periodo == "semana":
from datetime import timedelta

inicio_semana = hoy - timedelta(days=hoy.weekday())
domain_fecha = [("fecha", ">=", inicio_semana), ("fecha", "<=", hoy)]
periodo_actual = f"Esta semana · desde {inicio_semana.strftime('%d/%m/%Y')}"

                elif periodo == "custom" and fecha_desde_raw and fecha_hasta_raw:
                    try:
                        desde = fields.Date.from_string(fecha_desde_raw)
                        hasta = fields.Date.from_string(fecha_hasta_raw)
                        domain_fecha = [("fecha", ">=", desde), ("fecha", "<=", hasta)]
                        periodo_actual = (
                            f"{desde.strftime('%d/%m/%Y')} — {hasta.strftime('%d/%m/%Y')}"
                        )
                    except Exception:
                        domain_fecha = []

                else:
                    # Default: mes actual
                    inicio_mes = hoy.replace(day=1)
                    domain_fecha = [("fecha", ">=", inicio_mes), ("fecha", "<=", hoy)]
                    periodo_actual = f"Este mes · {hoy.strftime('%B %Y')}"

                    # ── Filtro de proyecto ───────────────────────────────────────────────
                    domain_proyecto = []
                    if proyecto_id_raw:
                        try:
                            pid = int(proyecto_id_raw)
                            # Verificar que el proyecto le pertenece al líder
                            if _get_proyecto_del_lider(pid, lider_id):
                                domain_proyecto = [("proyecto_id", "=", pid)]
                        except (ValueError, TypeError):
                            pass

                        # ── KPIs ─────────────────────────────────────────────────────────────
                        domain_extra = domain_fecha + domain_proyecto
                        kpis = _calcular_kpis(lider_id, domain_extra)

                        # ── Últimos 10 registros ─────────────────────────────────────────────
                        Registro = request.env["digitalizacion.registro"].sudo()
                        domain_registros = (
                            [("lider_id", "=", lider_id)] + domain_fecha + domain_proyecto
                        )
                        ultimos_registros = Registro.search(
                            domain_registros,
                            order="fecha desc, id desc",
                            limit=10,
                        )

                        # ── Asignaciones activas del líder ───────────────────────────────────
                        asignaciones = _get_asignaciones_activas(lider_id)

                        # ── Miembros del equipo (filtrados por proyecto seleccionado) ─────
                        miembros_equipo = request.env["digitalizacion.miembro_proyecto"].sudo().browse()
                        proyecto_ref = None
                        if domain_proyecto and asignaciones:
                            # Usar el proyecto seleccionado en el filtro
                            try:
                                pid = int(proyecto_id_raw)
                                proyecto_ref = _get_proyecto_del_lider(pid, lider_id)
                            except (ValueError, TypeError):
                                pass
                            if not proyecto_ref and asignaciones:
                                proyecto_ref = asignaciones[0].proyecto_id
                                if proyecto_ref:
                                    miembros_equipo = (
                                        request.env["digitalizacion.miembro_proyecto"]
                                        .sudo()
                                        .search(
                                            [
                                                ("proyecto_id", "=", proyecto_ref.id),
                                                ("active", "=", True),
                                                ("fecha_salida", "=", False),
                                            ]
                                        )
                                    )

                                    # ── Resumen por etapa (dato dinámico para gráfico de barras) ──────
                                    resumen_etapas = []
                                    registros_resumen = Registro.search(domain_registros)
                                    conteo_etapa = {}
                                    for rec in registros_resumen:
                                        nombre = rec.etapa_id.name or "Sin etapa"
                                        conteo_etapa[nombre] = conteo_etapa.get(nombre, 0) + (
                                            rec.produccion_principal or 0
                                        )
                                        if conteo_etapa:
                                            max_val = max(conteo_etapa.values()) or 1
                                            resumen_etapas = [
                                                {
                                                    "nombre": nombre,
                                                    "cantidad": cantidad,
                                                    "porcentaje": round((cantidad / max_val) * 100),
                                                }
                                                for nombre, cantidad in sorted(conteo_etapa.items())
                                            ]

                                            valores = {
                                                "kpis": kpis,
                                                "ultimos_registros": ultimos_registros,
                                                "asignaciones": asignaciones,
                                                "miembros_equipo": miembros_equipo,
                                                "resumen_etapas": resumen_etapas,
                                                "periodo_actual": periodo_actual,
                                                "page_name": "digitalizacion_dashboard",
                                            }

                                            return request.render("digitalizacion.wf02_dashboard", valores)

                                                # =========================================================================
                                                # FORMULARIO MULTI-FILA "REGISTRAR TRABAJO"
                                                # GET /digitalizacion/registro/<proyecto_id>
                                                # =========================================================================

    @http.route(
        "/digitalizacion/registro/<int:proyecto_id>",
        type="http",
        auth="user",
        website=True,
        methods=["GET"],
    )
    def formulario_registro(self, proyecto_id: int, **kwargs):
        """
        Formulario para registrar la producción del equipo al final de la jornada.

        Verifica que el líder en sesión tenga una asignación activa al proyecto_id.

        Variables renderizadas:
            proyecto       → digitalizacion.proyecto record
            etapas_json    → JSON string [{id, name}, ...]  (T-01)
            miembros_json  → JSON string [{id, name}, ...]  (T-05, miembros activos del proyecto)
            escaneres_json → JSON string [{id, name}, ...]  (T-02)
            """
            try:
                _verificar_lider()
            except AccessError:
                return request.redirect("/web/login")

            lider_id = request.env.user.id

            # Verificar que el proyecto es del líder
            proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
            if not proyecto:
                return request.redirect("/digitalizacion")

            # ── Etapas activas (T-01) ────────────────────────────────────────────
            etapas = (
                request.env["digitalizacion.etapa"]
                .sudo()
                .search(
                    [("active", "=", True)],
                    order="sequence asc, name asc",
                )
            )
            etapas_json = json.dumps([{"id": e.id, "name": e.name} for e in etapas])

            # ── Miembros activos del proyecto (T-05) ─────────────────────────────
            # Excluye miembros con fecha_salida registrada
            miembros = (
                request.env["digitalizacion.miembro_proyecto"]
                .sudo()
                .search(
                    [
                        ("proyecto_id", "=", proyecto_id),
                        ("active", "=", True),
                        ("fecha_salida", "=", False),
                    ],
                    order="partner_name asc",
                )
            )

            miembros_json = json.dumps(
                [{"id": m.id, "name": m.partner_id.name} for m in miembros]
            )

            # ── Tipos de escáner activos (T-02) ──────────────────────────────────
            escaneres = (
                request.env["digitalizacion.tipo_escaner"]
                .sudo()
                .search(
                    [("active", "=", True)],
                    order="name asc",
                )
            )
            escaneres_json = json.dumps([{"id": e.id, "name": e.name} for e in escaneres])

            valores = {
                "proyecto": proyecto,
                "etapas_json": etapas_json,
                "miembros_json": miembros_json,
                "escaneres_json": escaneres_json,
                "page_name": "digitalizacion_formulario",
            }

            return request.render("digitalizacion.wf03_formulario", valores)

            # =========================================================================
            # API — GUARDADO MASIVO DE REGISTROS
            # POST /digitalizacion/api/guardar_registros
            # =========================================================================

    @http.route(
        "/digitalizacion/api/guardar_registros",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
def api_guardar_registros(
    self,
    proyecto_id: int,
    filas: list,
    fecha: str = None,
    **kwargs,
):
    """
    Crea en lote los registros de trabajo (digitalizacion.registro).

    Payload esperado (JSON-RPC params):
        {
            "proyecto_id": 5,
            "fecha": "2026-03-05",          ← opcional, default hoy
            "filas": [
                {
                    "miembro_id":          12,  ← ID de digitalizacion.miembro_proyecto (T-05)
                    "etapa_id":              3,
                    "no_caja":          "504A, 504B",
                    "cantidad_cajas":        2,
                    "no_expedientes": 45,
                    "total_folios":      120,
                    "total_escaneos":         130,
                    "tipo_escaner_ids":    [1, 2],   ← lista de IDs (Many2many)
                    "expedientes_editados":  0,
                    "folios_editados":       0,
                    "expedientes_indexados": 0,
                    "folios_indexados":      0,
                    "observacion":        "..."
                },
                ...
            ]
        }

        Respuesta exitosa:
            {"status": "success", "creados": N}

            Respuesta de error:
                {"status": "error", "message": "..."}
                """
                try:
                    _verificar_lider()
                except AccessError:
                    return {"status": "error", "message": "Acceso denegado."}

                lider = request.env.user
                lider_id = lider.id

                # ── Validar proyecto ─────────────────────────────────────────────────
                proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
                if not proyecto:
                    return {
                "status": "error",
                "message": "Proyecto no encontrado o sin acceso.",
            }

            # ── Fecha del registro ───────────────────────────────────────────────
            if fecha:
                try:
                    fecha_registro = fields.Date.from_string(fecha)
                except Exception:
                    fecha_registro = date.today()
            else:
                fecha_registro = date.today()

                # ── Validar que filas no esté vacío ──────────────────────────────────
                if not filas or not isinstance(filas, list):
                    return {
                "status": "error",
                "message": "No se recibieron filas para guardar.",
            }

            Registro = request.env["digitalizacion.registro"].sudo()
            Miembro = request.env["digitalizacion.miembro_proyecto"].sudo()
            Etapa = request.env["digitalizacion.etapa"].sudo()

            creados = 0
            errores = []

            for idx, fila in enumerate(filas, start=1):
                # Campos obligatorios por fila
                miembro_id = fila.get("miembro_id")  # ID de miembro_proyecto (T-05)
                etapa_id = fila.get("etapa_id")

                if not miembro_id or not etapa_id:
                    errores.append(
                        f"Fila {idx}: 'miembro_id' y 'etapa_id' son obligatorios."
                    )
                    continue

                # Verificar que el miembro pertenece al proyecto
                miembro = Miembro.search(
                    [
                        ("id", "=", miembro_id),
                        ("proyecto_id", "=", proyecto_id),
                        ("active", "=", True),
                        ("fecha_salida", "=", False),
                    ],
                    limit=1,
                )

                if not miembro:
                    errores.append(
                        f"Fila {idx}: El digitalizador ID {miembro_id} "
                        f"no es miembro activo del proyecto."
                    )
                    continue

                # Verificar etapa válida
                etapa = Etapa.browse(etapa_id)
                if not etapa.exists() or not etapa.active:
                    errores.append(f"Fila {idx}: Etapa ID {etapa_id} no válida o inactiva.")
                    continue

                # ── Construir valores del registro ───────────────────────────────
                # tipo_escaner_ids: el JS puede enviar un escalar o una lista
                tipo_escaner_raw = fila.get("tipo_escaner_ids", fila.get("tipo_escaner_id", []))
                if not isinstance(tipo_escaner_raw, list):
                    tipo_escaner_raw = [tipo_escaner_raw] if tipo_escaner_raw else []
                    # Many2many command: [(6, 0, [id1, id2, ...])]
                    tipo_escaner_m2m = [(6, 0, [int(x) for x in tipo_escaner_raw if x])]

                    vals = {
                        # Auditoría: siempre el líder en sesión
                        "lider_id": lider_id,
                        # Relaciones
                        "miembro_id": miembro_id,
                        "proyecto_id": proyecto_id,
                        "etapa_id": etapa_id,
                        # Temporal
                        "fecha": fecha_registro,
                        "hora": fields.Datetime.now(),
                        # Campos comunes
                        "no_caja": fila.get("no_caja", ""),
                        "observacion": fila.get("observacion", ""),
                        # Campos por etapa — los que no aplican quedan en 0/None (NULL en BD)
                        "cantidad_cajas": int(fila.get("cantidad_cajas") or 0) or None,
                        "no_expedientes": int(fila.get("no_expedientes") or 0) or None,
                        "total_folios": int(fila.get("total_folios") or 0) or None,
                        "total_escaneos": int(fila.get("total_escaneos") or 0) or None,
                        "tipo_escaner_ids": tipo_escaner_m2m,
                    }

                    try:
                        Registro.create(vals)
                        creados += 1
                    except (ValidationError, UserError) as e:
                        errores.append(f"Fila {idx}: {str(e)}")
                    except Exception:
                        _logger.exception("Error inesperado al crear registro fila %d", idx)
                        errores.append(f"Fila {idx}: Error interno al guardar.")

                        if errores and creados == 0:
                            # To-dos fallaron
                            return {
                        "status": "error",
                        "message": " | ".join(errores),
                    }

                    response = {"status": "success", "creados": creados}
                    if errores:
                        # Guardado parcial
                        response["advertencias"] = errores

                        return response

                    # =========================================================================
                    # API — BÚSQUEDA DE CONTACTOS (res.partner)
                    # POST /digitalizacion/api/buscar_partner
                    # =========================================================================

    @http.route(
        "/digitalizacion/api/buscar_partner",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def api_buscar_partner(self, term: str = "", **kwargs):
        """
        Busca contactos en res.partner por nombre (búsqueda aproximada ilike).
        Usado por el modal "Agregar miembro al proyecto" del WF-03.

        Params: { "term": "Pedro S" }

        Respuesta:
            {
                "partners": [
                    {"id": 42, "name": "Pedro Sandoval", "email": "..."},
                    ...
                ]
            }

            Devuelve máximo 10 resultados para no sobrecargar la UI.
            Excluye contactos que ya son miembros del proyecto indicado (si se pasa proyecto_id).
            """
            try:
                _verificar_lider()
            except AccessError:
                return {"partners": [], "error": "Acceso denegado."}

            if not term or len(term.strip()) < 2:
                return {"partners": []}

            # proyecto_id opcional para excluir ya-miembros
            proyecto_id = kwargs.get("proyecto_id")

            Partner = request.env["res.partner"].sudo()
            domain = [
                ("name", "ilike", term.strip()),
                ("active", "=", True),
            ]

            # Excluir partners que ya son miembros del proyecto
            if proyecto_id:
                try:
                    pid = int(proyecto_id)
                    miembros_existentes = (
                        request.env["digitalizacion.miembro_proyecto"]
                        .sudo()
                        .search(
                            [
                                ("proyecto_id", "=", pid),
                                ("active", "=", True),
                            ]
                        )
                    )
                    partner_ids_excluir = miembros_existentes.mapped("partner_id").ids
                    if partner_ids_excluir:
                        domain.append(("id", "not in", partner_ids_excluir))
                except (ValueError, TypeError):
                    pass

                partners = Partner.search(domain, limit=10, order="name asc")

                return {
                "partners": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "email": p.email or "",
                    }
                    for p in partners
                ]
            }

            # =========================================================================
            # API — BÚSQUEDA DE USUARIOS ODOO (res.users)
            # POST /digitalizacion/api/buscar_usuario
            # =========================================================================

    @http.route(
        "/digitalizacion/api/buscar_usuario",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def api_buscar_usuario(self, term: str = "", **kwargs):
        """
        Busca contactos (res.partner) por nombre para vincular como miembros.
        Devuelve id (partner_id), nombre y email.

        Params: { "term": "Ana" }

        Respuesta:
            {
                "usuarios": [
                    {"id": 5, "name": "Ana García", "login": "ana@otec.cl"},
                    ...
                ]
            }
            """
            try:
                _verificar_lider()
            except AccessError:
                return {"usuarios": [], "error": "Acceso denegado."}

            if not term or len(term.strip()) < 2:
                return {"usuarios": []}

            # Buscar en res.partner (contactos), NO en res.users internos
            Partner = request.env["res.partner"].sudo()
            domain = [
                ("name", "ilike", term.strip()),
                ("active", "=", True),
            ]

            partners = Partner.search(domain, limit=10, order="name asc")

            return {
            "usuarios": [
                {
                    "id": p.id,
                    "name": p.name,
                    "login": p.email or "",
                }
                for p in partners
            ]
        }

        # =========================================================================
        # API — AGREGAR MIEMBRO AL PROYECTO (digitalizacion.miembro_proyecto)
        # POST /digitalizacion/api/agregar_miembro
        # =========================================================================

    @http.route(
        "/digitalizacion/api/agregar_miembro",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
def api_agregar_miembro(
    self,
    proyecto_id: int,
    partner_id: int = None,
    miembro_id: int = None,
    nombre_nuevo: str = None,
    fecha_asignacion: str = None,
    **kwargs,
):
    """
    Vincula un contacto (res.partner) a un proyecto como miembro del equipo.

    Implementa la lógica de negocio descrita en nota 3.7:
        1. Si partner_id viene informado → usar partner existente directamente.
        2. Si nombre_nuevo viene informado → buscar en res.partner.
        a. Si existe único match exacto → usar ese.
        b. Si no existe → crear res.partner nuevo.
        3. Crear digitalizacion.miembro_proyecto (T-05).
        4. Validar UNIQUE(proyecto_id, partner_id). Devolver error si duplicado.

        Params:
            {
                "proyecto_id":       5,
                "partner_id":        42,           ← ID res.partner (opcional)
                "nombre_nuevo":      "Pedro López", ← nombre a buscar/crear (opcional)
                "fecha_asignacion":  "2026-03-05"  ← opcional, default hoy
            }

            Respuesta exitosa:
                {
                    "status":  "success",
                    "miembro": {"id": 99, "name": "Pedro López"}
                }
                """
                try:
                    _verificar_lider()
                except AccessError:
                    return {"status": "error", "message": "Acceso denegado."}

                lider_id = request.env.user.id

                # ── Verificar acceso al proyecto ─────────────────────────────────────
                proyecto = _get_proyecto_del_lider(proyecto_id, lider_id)
                if not proyecto:
                    return {
                "status": "error",
                "message": "Proyecto no encontrado o sin acceso.",
            }

            Partner = request.env["res.partner"].sudo()
            Miembro = request.env["digitalizacion.miembro_proyecto"].sudo()

            # ── Resolver el partner ──────────────────────────────────────────────
            partner = None

            # compatibilidad con viejo partner_id o nuevo miembro_id enviado del frontend
            partner_id_final = partner_id or miembro_id

            if partner_id_final:
                # Caso 1: partner_id explícito (seleccionado desde resultados de búsqueda)
                partner = Partner.browse(partner_id_final)
                if not partner.exists():
                    return {
                "status": "error",
                "message": f"El contacto ID {partner_id_final} no existe.",
            }

                elif nombre_nuevo:
                    nombre_limpio = nombre_nuevo.strip()
                    if not nombre_limpio:
                        return {"status": "error", "message": "El nombre no puede estar vacío."}

                    # Caso 2a: buscar por nombre exacto (case-insensitive)
                    partner_existente = Partner.search(
                        [("name", "=ilike", nombre_limpio), ("active", "=", True)],
                        limit=1,
                    )

                    if partner_existente:
                        partner = partner_existente
                    else:
                        # Caso 2b: crear nuevo res.partner
                        try:
                            partner = Partner.create({"name": nombre_limpio})
                            _logger.info(
                                "Nuevo res.partner creado desde portal: %s (ID %d)",
                                nombre_limpio,
                                partner.id,
                            )
                        except Exception as e:
                            _logger.exception("Error al crear res.partner '%s'", nombre_limpio)
                            return {
                        "status": "error",
                        "message": f"No se pudo crear el contacto: {str(e)}",
                    }
                    else:
                        return {
                    "status": "error",
                    "message": "Debes indicar 'partner_id' o 'nombre_nuevo'.",
                }

                # ── Validar restricción UNIQUE(proyecto_id, partner_id) ──────────────
                duplicado = Miembro.search(
                    [
                        ("proyecto_id", "=", proyecto_id),
                        ("partner_id", "=", partner.id),
                    ],
                    limit=1,
                )

                if duplicado:
                    return {
                "status": "error",
                "message": f"'{partner.name}' ya es miembro del proyecto '{proyecto.name}'.",
            }

            # ── Crear registro en digitalizacion.miembro_proyecto ────────────────
            if fecha_asignacion:
                try:
                    fecha_obj = fields.Date.from_string(fecha_asignacion)
                except Exception:
                    fecha_obj = date.today()
            else:
                fecha_obj = date.today()

                try:
                    nuevo_miembro = Miembro.create(
                        {
                            "proyecto_id": proyecto_id,
                            "partner_id": partner.id,
                            "fecha_integracion": fecha_obj,
                            "active": True,
                        }
                    )
                except (ValidationError, UserError) as e:
                    return {"status": "error", "message": str(e)}
            except Exception:
                _logger.exception(
                    "Error al crear digitalizacion.miembro_proyecto para partner %d en proyecto %d",
                    partner.id,
                    proyecto_id,
                )
                return {"status": "error", "message": "Error interno al agregar miembro."}

            return {
            "status": "success",
            "miembro": {
                "id": nuevo_miembro.id,
                "name": partner.name,
            },
        }

        # =========================================================================
        # Portal home — contador para el home del portal (/home)
        # Hereda CustomerPortal para inyectar digitalizacion_count
        # =========================================================================


class DigitalizacionPortalHome(CustomerPortal):
    """
    Inyecta el contador de registros en el home del portal extendiendo CustomerPortal.
    Esto permite que la plantilla 'portal_my_digitalizacion_home_menu' reciba
    la variable 'digitalizacion_count' y muestre el acceso directo.
    """

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        # Solo calculamos si el lider está logueado y tiene el grupo correcto
        if request.env.user.has_group("digitalizacion.group_digitalizacion_lider"):
            lider_id = request.env.user.id
            values["digitalizacion_count"] = (
                request.env["digitalizacion.registro"]
                .sudo()
                .search_count([("lider_id", "=", lider_id)])
            )
        else:
            values["digitalizacion_count"] = 0

            return values