/** @odoo-module **/

import { Component, useState, xml, mount } from "@odoo/owl";
import publicWidget from "@web/legacy/js/public/public_widget";

// ============= CONSTANTES =============
const REGLAS_ETAPA = {
  limpieza: {
    caja: true,
    expedientes: true,
    folios: true,
    escaneos: false,
    escaner: false,
    expIndexados: false,
    foliosIndexados: false,
  },
  ordenado: {
    caja: true,
    expedientes: true,
    folios: true,
    escaneos: false,
    escaner: false,
    expIndexados: false,
    foliosIndexados: false,
  },
  digitalizado: {
    caja: true,
    expedientes: true,
    folios: true,
    escaneos: true,
    escaner: true,
    expIndexados: false,
    foliosIndexados: false,
  },
  editado: {
    caja: true,
    expedientes: false,
    folios: true,
    escaneos: false,
    escaner: false,
    expIndexados: false,
    foliosIndexados: false,
  },
  indexado: {
    caja: false,
    expedientes: false,
    folios: false,
    escaneos: false,
    escaner: false,
    expIndexados: true,
    foliosIndexados: true,
  },
};

const REGLA_POR_DEFECTO = {
  caja: true,
  expedientes: true,
  folios: true,
  escaneos: false,
  escaner: false,
  expIndexados: false,
  foliosIndexados: false,
};

const CAMPOS_NUMERICOS = [
  { clave: "no_expedientes", regla: "expedientes" },
  { clave: "total_folios", regla: "folios" },
  { clave: "total_escaneos", regla: "escaneos" },
  { clave: "expedientes_indexados", regla: "expIndexados" },
  { clave: "folios_indexados", regla: "foliosIndexados" },
];

const LIMITES = {
  MAX_NUMERO: 999999,
  MAX_OBSERVACION: 500,
};

// ============= UTILIDADES =============
const UtilidadFecha = {
  obtenerHoy() {
    const hoy = new Date();
    const diferenciaZona = hoy.getTimezoneOffset();
    const local = new Date(hoy.getTime() - diferenciaZona * 60 * 1000);
    return local.toISOString().split("T")[0];
  },
};

// ============= VALIDADORES =============
class ValidadorFila {
  constructor(funcionObtenerReglas) {
    this.obtenerReglas = funcionObtenerReglas;
  }

  validar(fila) {
    const errores = {};
    let esValido = true;

    // Validar digitalizador
    if (!fila.miembro_id) {
      errores.miembro = "Por favor, seleccione un digitalizador.";
      esValido = false;
    }

    // Validar etapa
    if (!fila.etapa_id) {
      errores.etapa = "Por favor, seleccione la etapa de trabajo.";
      return { errores, esValido: false };
    }

    const reglas = this.obtenerReglas(fila.etapa_id);

    // Validar campos específicos
    esValido =
      this._validarCamposEspecificos(fila, reglas, errores) && esValido;
    esValido = this._validarProduccion(fila, reglas, errores) && esValido;
    esValido = this._validarEscaner(fila, reglas, errores) && esValido;
    esValido = this._validarObservacion(fila, errores) && esValido;

    return { errores, esValido };
  }

  _validarCamposEspecificos(fila, reglas, errores) {
    let esValido = true;

    // Validar referencia de cajas
    if (reglas.caja && fila.referencia_cajas) {
      const ref = fila.referencia_cajas.trim();
      if (!/[a-zA-Z0-9]/.test(ref)) {
        errores.referencia_cajas =
          "No puede contener solo caracteres vacíos o símbolos especiales. Debe ingresar texto o números.";
        esValido = false;
      }
    }

    // Validar campos numéricos
    CAMPOS_NUMERICOS.forEach(({ clave, regla }) => {
      if (reglas[regla]) {
        esValido = this._validarNumero(fila, clave, errores) && esValido;
      }
    });

    return esValido;
  }

  _validarNumero(fila, campo, errores) {
    let valor = fila[campo];

    if (
      valor === "" ||
      valor === null ||
      valor === undefined ||
      Number.isNaN(Number(valor))
    ) {
      fila[campo] = 0;
      valor = 0;
    }

    const num = Number(valor);

    if (!Number.isInteger(num)) {
      errores[campo] =
        `El valor ingresado no es un número entero. No se permiten decimales.`;
      return false;
    }

    if (num < 0) {
      errores[campo] = `No se permiten cantidades negativas en la producción.`;
      return false;
    }

    if (num > LIMITES.MAX_NUMERO) {
      errores[campo] =
        `La cantidad excede el límite permitido por registro (Máx. ${LIMITES.MAX_NUMERO.toLocaleString()}).`;
      return false;
    }

    return true;
  }

  _validarProduccion(fila, reglas, errores) {
    const hayProduccion = CAMPOS_NUMERICOS.some(
      ({ clave, regla }) => reglas[regla] && fila[clave] > 0,
    );

    if (!hayProduccion) {
      errores.produccion =
        "Todos los campos numéricos están en cero. Debe registrar cantidades.";
      return false;
    }

    return true;
  }

  _validarEscaner(fila, reglas, errores) {
    if (
      reglas.escaner &&
      (!fila.tipo_escaner_ids || fila.tipo_escaner_ids.length === 0)
    ) {
      errores.escaner =
        "Digitalización requiere que especifique al menos 1 escáner usado en la operación.";
      return false;
    }
    return true;
  }

  _validarObservacion(fila, errores) {
    if (fila.observacion && fila.observacion.length > LIMITES.MAX_OBSERVACION) {
      errores.observacion = `La observación (${fila.observacion.length} caracteres) excede el máximo (${LIMITES.MAX_OBSERVACION}).`;
      return false;
    }
    return true;
  }
}

// ============= GESTOR DE FILAS =============
class GestorFila {
  constructor(funcionObtenerId) {
    this.obtenerSiguienteId = funcionObtenerId;
  }

  crearVacia() {
    return {
      id: this.obtenerSiguienteId(),
      miembro_id: "",
      etapa_id: "",
      referencia_cajas: "",
      no_expedientes: 0,
      total_folios: 0,
      total_escaneos: 0,
      tipo_escaner_ids: [],
      expedientes_indexados: 0,
      folios_indexados: 0,
      observacion: "",
      errores: {},
    };
  }

  limpiarParaGuardar(fila) {
    const copia = { ...fila };
    delete copia.errores;
    return copia;
  }

  reiniciarCamposPorEtapa(fila, reglas) {
    const camposPorRegla = {
      caja: "referencia_cajas",
      expedientes: "no_expedientes",
      folios: "total_folios",
      escaneos: "total_escaneos",
      escaner: "tipo_escaner_ids",
      expIndexados: "expedientes_indexados",
      foliosIndexados: "folios_indexados",
    };

    Object.entries(camposPorRegla).forEach(([regla, campo]) => {
      if (!reglas[regla]) {
        if (Array.isArray(fila[campo])) {
          fila[campo] = [];
        } else {
          fila[campo] = campo === "referencia_cajas" ? "" : 0;
        }
      }
    });
  }

  alternarEscaner(fila, escanerId, seleccionado) {
    if (!Array.isArray(fila.tipo_escaner_ids)) {
      fila.tipo_escaner_ids = [];
    }

    const id = Number(escanerId);
    if (seleccionado) {
      if (!fila.tipo_escaner_ids.includes(id)) {
        fila.tipo_escaner_ids = [...fila.tipo_escaner_ids, id];
      }
    } else {
      fila.tipo_escaner_ids = fila.tipo_escaner_ids.filter((v) => v !== id);
    }
  }
}

// ============= SERVICIO API =============
class ServicioApi {
  constructor(proyectoId) {
    this.proyectoId = proyectoId;
  }

  async guardarRegistros(fecha, filas) {
    const respuesta = await fetch(
      `/digitalizacion/api/v1/proyectos/${this.proyectoId}/registros`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          params: { fecha: fecha, registros: filas },
        }),
      },
    );
    return await respuesta.json();
  }
}

// ============= COMPONENTE PRINCIPAL =============
export class RegistroForm extends Component {
  static template = xml`
    <div class="o_digitalizacion_form_wrapper mt-3">
        <!-- Alertas dinámicas Globales -->
        <div t-if="state.alerta" t-attf-class="alert alert-{{ state.alerta.tipo }} alert-dismissible shadow-sm border-0 fade show mb-4 rounded-3 p-3 d-flex align-items-center" role="alert">
            <i t-attf-class="fa {{ state.alerta.tipo == 'success' ? 'fa-check-circle' : 'fa-exclamation-circle' }} me-3 fa-lg opacity-75"/>
            <div class="flex-grow-1 fw-semibold text-break"><t t-esc="state.alerta.mensaje"/></div>
            <button t-on-click="() => this.state.alerta = null" type="button" class="btn-close shadow-none" aria-label="Close"/>
        </div>

        <div class="card border-0 bg-transparent">
            <!-- Jumbotron de Producción -->
            <div class="d-flex flex-column flex-md-row align-items-md-end justify-content-between mb-4 gap-3 bg-white p-4 rounded-4 shadow-sm border border-light">
                <div>
                   <h1 class="h4 mb-1 fw-bold text-dark text-uppercase tracking-tight">Registro de Producción Diaria</h1>
                   <p class="text-muted small mb-0 fw-medium">Complete los datos solicitados. Los campos obligatorios están marcados con un asterisco (*).</p>
                </div>
                <div class="d-flex flex-column gap-1">
                    <label for="fecha_reporte" class="small fw-bold text-dark text-uppercase opacity-75">Fecha reportada: *</label>
                    <input id="fecha_reporte" name="fecha_reporte" t-att-max="this.obtenerHoy()" t-model="state.fecha" type="date" class="form-control border-light shadow-none bg-light p-2 ps-3 fw-bold rounded-3" style="width: 170px; cursor: pointer;"/>
                </div>
            </div>

            <!-- Listado de Filas por Producción -->
            <div class="o_digitalizacion_cards_list">
                <t t-foreach="state.filas" t-as="fila" t-key="fila.id">
                    <t t-set="reglas" t-value="this.obtenerReglasVisibilidad(fila.etapa_id)"/>
                    <div class="card o_digitalizacion_record_card mb-4" t-attf-style="border-left: 5px solid {{ fila.etapa_id ? 'var(--dig-primary)' : '#e5e7eb' }} !important;">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0 fw-bold text-muted text-uppercase tracking-wider small"><i class="fa fa-list-alt me-2 text-primary opacity-75"/> LÍNEA DE PRODUCCIÓN #<t t-esc="fila.id"/></h6>
                            <button t-on-click="() => this.eliminarFila(fila.id)" type="button" class="btn btn-sm btn-link text-danger border-0 p-2 opacity-50-hover text-decoration-none" title="Eliminar registro"><i class="fa fa-trash-o fa-lg" aria-hidden="true"/></button>
                        </div>

                        <div class="card-body bg-white pt-4">
                            <!-- BLOQUE 1: Identificación -->
                            <div class="row g-4 mb-4 pb-4 border-bottom border-light">
                                <div class="col-md-6">
                                    <label t-attf-for="miembro_{{fila.id}}" class="small fw-bold text-dark text-uppercase mb-2 d-block">1. Digitalizador *</label>
                                    <select t-attf-id="miembro_{{fila.id}}" t-attf-name="miembro_{{fila.id}}" t-model.number="fila.miembro_id" t-on-change="() => this.validarYActualizar(fila)" t-attf-class="form-select p-2 fw-bold text-dark {{ fila.errores?.miembro ? 'is-invalid-field' : '' }}">
                                        <option value="">Seleccionar integrante del equipo...</option>
                                        <t t-foreach="props.miembros" t-as="m" t-key="m.id">
                                            <option t-att-value="m.id" t-esc="m.name"/>
                                        </t>
                                    </select>
                                    <div t-if="fila.errores?.miembro" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.miembro"/></div>
                                </div>
                                <div class="col-md-6">
                                    <label t-attf-for="etapa_{{fila.id}}" class="small fw-bold text-dark text-uppercase mb-2 d-block">2. Etapa de trabajo *</label>
                                    <select t-attf-id="etapa_{{fila.id}}" t-attf-name="etapa_{{fila.id}}" t-model.number="fila.etapa_id" t-on-change="() => { this.alCambiarEtapa(fila); this.validarYActualizar(fila); }" t-attf-class="form-select p-2 fw-bold {{ fila.etapa_id ? 'bg-primary text-white' : 'text-dark' }} {{ fila.errores?.etapa ? 'is-invalid-field' : '' }}">
                                        <option value="">— Elegir etapa a reportar —</option>
                                        <t t-foreach="props.etapas" t-as="e" t-key="e.id">
                                            <option t-att-value="e.id" t-esc="e.name"/>
                                        </t>
                                    </select>
                                    <div t-if="fila.errores?.etapa" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.etapa"/></div>
                                </div>
                            </div>

                            <!-- BLOQUE 2: Producción -->
                            <div class="row g-4">
                                <t t-if="reglas.caja or reglas.expedientes or reglas.folios or reglas.escaneos">
                                    <div class="col-12 col-md-6 border-end-md border-light">
                                        <div class="o_digitalizacion_section_label">Recolección de Archivos</div>
                                        <div class="row g-3">
                                            <div t-if="reglas.caja" class="col-12 mb-2">
                                                <label t-attf-for="ref_{{fila.id}}" class="small fw-bold text-dark mb-1 d-block">Referencia de Cajas</label>
                                                <input t-attf-id="ref_{{fila.id}}" t-attf-name="ref_{{fila.id}}" t-model="fila.referencia_cajas" t-on-blur="() => this.validarYActualizar(fila)" t-on-keyup="() => this.validarYActualizar(fila)" type="text" t-attf-class="form-control p-2 bg-light {{ fila.errores?.referencia_cajas ? 'is-invalid-field' : '' }}" placeholder="Ej: BF202, BF199..."/>
                                                <div t-if="fila.errores?.referencia_cajas" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.referencia_cajas"/></div>
                                            </div>
                                            <div t-if="reglas.expedientes" class="col-6">
                                                <label t-attf-for="exp_{{fila.id}}" class="small fw-bold text-dark mb-1 d-block">Cantidad de expedientes</label>
                                                <input t-attf-id="exp_{{fila.id}}" t-attf-name="exp_{{fila.id}}" t-model.number="fila.no_expedientes" t-on-blur="() => this.validarYActualizar(fila)" t-on-keyup="() => this.validarYActualizar(fila)" type="number" step="1" min="0" t-attf-class="form-control p-2 text-center bg-light {{ fila.errores?.no_expedientes ? 'is-invalid-field' : '' }}" placeholder="0"/>
                                                <div t-if="fila.errores?.no_expedientes" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.no_expedientes"/></div>
                                            </div>
                                            <div t-if="reglas.folios" class="col-6">
                                                <label t-attf-for="fol_{{fila.id}}" class="small fw-bold text-dark mb-1 d-block">Cantidad de folios</label>
                                                <input t-attf-id="fol_{{fila.id}}" t-attf-name="fol_{{fila.id}}" t-model.number="fila.total_folios" t-on-blur="() => this.validarYActualizar(fila)" t-on-keyup="() => this.validarYActualizar(fila)" type="number" step="1" min="0" t-attf-class="form-control p-2 text-center bg-light {{ fila.errores?.total_folios ? 'is-invalid-field' : '' }}" placeholder="0"/>
                                                <div t-if="fila.errores?.total_folios" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.total_folios"/></div>
                                            </div>
                                            <div t-if="reglas.escaneos" class="col-12 mt-3">
                                                <div class="p-3 rounded-3 border border-light bg-light">
                                                    <label t-attf-for="esc_{{fila.id}}" class="small fw-bold text-primary mb-2 d-block text-uppercase">Número de escaneos</label>
                                                    <input t-attf-id="esc_{{fila.id}}" t-attf-name="esc_{{fila.id}}" t-model.number="fila.total_escaneos" t-on-blur="() => this.validarYActualizar(fila)" t-on-keyup="() => this.validarYActualizar(fila)" type="number" step="1" min="0" t-attf-class="form-control form-control-lg border-primary border-opacity-25 text-center text-primary fw-bold {{ fila.errores?.total_escaneos ? 'is-invalid-field' : '' }}" placeholder="0"/>
                                                    <div t-if="fila.errores?.total_escaneos" class="text-danger small mt-2 fw-bold slide-in text-start"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.total_escaneos"/></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </t>

                                <t t-if="reglas.expIndexados or reglas.foliosIndexados">
                                    <div class="col-12 col-md-6">
                                        <div class="o_digitalizacion_section_label text-primary text-opacity-75">Indexación</div>
                                        <div class="row g-3">
                                            <div t-if="reglas.expIndexados" class="col-6">
                                                <label t-attf-for="ind_exp_{{fila.id}}" class="small fw-bold text-primary-emphasis mb-1 d-block">Expedientes indexados</label>
                                                <input t-attf-id="ind_exp_{{fila.id}}" t-attf-name="ind_exp_{{fila.id}}" t-model.number="fila.expedientes_indexados" t-on-blur="() => this.validarYActualizar(fila)" t-on-keyup="() => this.validarYActualizar(fila)" type="number" step="1" min="0" t-attf-class="form-control p-2 text-center bg-light {{ fila.errores?.expedientes_indexados ? 'is-invalid-field' : '' }}" placeholder="0"/>
                                                <div t-if="fila.errores?.expedientes_indexados" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.expedientes_indexados"/></div>
                                            </div>
                                            <div t-if="reglas.foliosIndexados" class="col-6">
                                                <label t-attf-for="ind_fol_{{fila.id}}" class="small fw-bold text-primary-emphasis mb-1 d-block">Folios indexados</label>
                                                <input t-attf-id="ind_fol_{{fila.id}}" t-attf-name="ind_fol_{{fila.id}}" t-model.number="fila.folios_indexados" t-on-blur="() => this.validarYActualizar(fila)" t-on-keyup="() => this.validarYActualizar(fila)" type="number" step="1" min="0" t-attf-class="form-control p-2 text-center bg-light {{ fila.errores?.folios_indexados ? 'is-invalid-field' : '' }}" placeholder="0"/>
                                                <div t-if="fila.errores?.folios_indexados" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.folios_indexados"/></div>
                                            </div>
                                        </div>
                                    </div>
                                </t>
                            </div>

                            <!-- Alerta de producción 0 dinámica -->
                            <div t-if="fila.errores?.produccion" class="alert alert-danger p-3 small mt-3 mb-0 fw-bold d-flex align-items-center slide-in">
                                <i class="fa fa-exclamation-circle fa-2x me-3"/> <t t-esc="fila.errores.produccion"/>
                            </div>

                            <!-- BLOQUE 3: Escáneres -->
                            <div t-if="reglas.escaner" class="col-12 mt-4 pt-3 border-top border-light border-opacity-50">
                                <label class="small fw-bold text-dark text-uppercase d-block mb-3">3. Equipos Utilizados <t t-if="fila.errores?.escaner"><span class="text-danger ms-2"><i class="fa fa-warning"/> Obligatorio</span></t></label>
                                <div class="d-flex flex-wrap gap-2 py-1">
                                    <t t-foreach="props.escaneres" t-as="escaner" t-key="escaner.id">
                                        <label t-attf-for="scanner_{{fila.id}}_{{escaner.id}}" t-attf-class="o_digitalizacion_escaner_chip mb-0 m-1 {{ fila.errores?.escaner ? 'is-invalid-chip' : '' }}">
                                            <input t-attf-id="scanner_{{fila.id}}_{{escaner.id}}" t-attf-name="scanner_{{fila.id}}_{{escaner.id}}" type="checkbox" class="d-none" t-att-checked="(fila.tipo_escaner_ids || []).includes(escaner.id)" t-on-change="(ev) => { this.alAlternarEscaner(fila, escaner.id, ev.target.checked); this.validarYActualizar(fila); }"/>
                                            <span class="fw-bold fs-small"><i t-attf-class="fa fa-hdd-o me-2" /> <t t-esc="escaner.name"/></span>
                                        </label>
                                    </t>
                                </div>
                                <div t-if="fila.errores?.escaner" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.escaner"/></div>
                            </div>

                            <!-- BLOQUE 4: Observaciones -->
                            <div class="col-12 mt-4 pt-3 border-top border-light border-opacity-50">
                                <label t-attf-for="obs_{{fila.id}}" class="small fw-bold text-dark text-uppercase mb-2 d-block">Observaciones Operativas</label>
                                <textarea t-attf-id="obs_{{fila.id}}" t-attf-name="obs_{{fila.id}}" t-model="fila.observacion" t-on-blur="() => this.validarYActualizar(fila)" t-attf-class="form-control bg-light p-3 pb-4 shadow-none {{ fila.errores?.observacion ? 'is-invalid-field' : '' }}" rows="2" placeholder="Opcional: Indique cualquier incidencia relevante durante la producción..."></textarea>
                                <div t-if="fila.errores?.observacion" class="text-danger small mt-2 fw-bold slide-in"><i class="fa fa-exclamation-triangle me-1"/> <t t-esc="fila.errores.observacion"/></div>
                            </div>
                        </div>
                    </div>
                </t>
            </div>

            <!-- Footer -->
            <div t-if="state.filas.length > 0" class="d-flex flex-column flex-md-row gap-3 justify-content-between align-items-center mt-2 bg-white p-4 rounded-4 shadow-sm border border-light">
                <button t-on-click="this.agregarFila" type="button" class="btn btn-outline-primary px-4 py-2 fw-bold w-100 w-md-auto shadow-none">
                    <i class="fa fa-plus-circle me-1" title="Agregar otro registro de producción"/> Agregar otro registro de producción
                </button>
                <div class="d-flex align-items-center gap-3 w-100 w-md-auto">
                    <button t-att-disabled="state.guardando" t-on-click="this.guardar" type="button" class="btn btn-primary shadow-sm px-5 py-3 btn-lg flex-grow-1 border-0 fw-bold shadow-md">
                        <i t-attf-class="fa {{ state.guardando ? 'fa-spinner fa-spin' : 'fa-save' }} me-2"/>
                        <t t-esc="state.guardando ? 'Guardando...' : 'Confirmar y Guardar'"/>
                    </button>
                </div>
            </div>
        </div>
    </div>
  `;

  // OWL, se define el estado inicial
  setup() {
    this.siguienteId = 1;
    this.state = useState({
      fecha: UtilidadFecha.obtenerHoy(),
      filas: [],
      alerta: null,
      guardando: false,
    });

    // Inicializar servicios
    this.gestorFila = new GestorFila(() => this.siguienteId++);
    this.validador = new ValidadorFila((etapaId) =>
      this.obtenerReglasVisibilidad(etapaId),
    );
    this.servicioApi = new ServicioApi(this.props.proyecto_id);

    // Crear primera fila
    this.state.filas = [this.gestorFila.crearVacia()];
  }

  // Métodos
  obtenerHoy() {
    return UtilidadFecha.obtenerHoy();
  }

  // Reglas de visibilidad por etapa
  obtenerReglasVisibilidad(etapaId) {
    if (!etapaId) return REGLA_POR_DEFECTO;
    const etapa = this.props.etapas.find((e) => e.id === etapaId);
    return REGLAS_ETAPA[etapa?.name?.toLowerCase()] || REGLA_POR_DEFECTO;
  }

  // Al cambiar etapa, reiniciar campos por etapa
  alCambiarEtapa(fila) {
    const reglas = this.obtenerReglasVisibilidad(fila.etapa_id);
    this.gestorFila.reiniciarCamposPorEtapa(fila, reglas);
  }

  // Al alternar escaner, reiniciar campos por etapa
  alAlternarEscaner(fila, escanerId, seleccionado) {
    this.gestorFila.alternarEscaner(fila, escanerId, seleccionado);
  }

  validarYActualizar(fila) {
    const { errores, esValido } = this.validador.validar(fila);
    fila.errores = errores;
    return esValido;
  }

  agregarFila() {
    this.state.filas.push(this.gestorFila.crearVacia());
  }

  eliminarFila(id) {
    this.state.filas = this.state.filas.filter((fila) => fila.id !== id);
  }

  // Guardar registros
  async guardar() {
    if (!this.state.fecha || this.state.filas.length === 0) return;

    let formularioTieneErrores = false;
    for (const fila of this.state.filas) {
      if (!this.validarYActualizar(fila)) formularioTieneErrores = true;
    }

    if (formularioTieneErrores) {
      this.state.alerta = {
        tipo: "danger",
        mensaje:
          "El formulario contiene errores. Corrija los campos marcados en rojo.",
      };
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    this.state.guardando = true;
    this.state.alerta = null;

    const filasLimpias = this.state.filas.map((f) =>
      this.gestorFila.limpiarParaGuardar(f),
    );

    try {
      const datos = await this.servicioApi.guardarRegistros(
        this.state.fecha,
        filasLimpias,
      );

      // Odoo JSON-RPC devuelve los errores en data.error
      if (datos.error) {
        let msg =
          datos.error.data?.message ||
          datos.error.message ||
          "Error del servidor";
        this.state.alerta = { tipo: "danger", mensaje: msg };
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      // El resultado exitoso o validación lógica está en data.result
      const resultado = datos.result;
      if (resultado?.success) {
        this.state.alerta = {
          tipo: "success",
          mensaje: `¡Reporte guardado! (${resultado.total} registro(s))`,
        };
        this.state.filas = [this.gestorFila.crearVacia()];
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else if (resultado?.error) {
        this.state.alerta = { tipo: "danger", mensaje: resultado.error };
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    } catch (error) {
      console.error("Error:", error);
      this.state.alerta = {
        tipo: "danger",
        mensaje: "Error de conexión. Intente nuevamente.",
      };
    } finally {
      this.state.guardando = false;
    }
  }
}

// ============= WIDGET =============
// OWL, se monta el componente, se le pasan los datos del widget y se renderiza
publicWidget.registry.DigitalizacionRegistro = publicWidget.Widget.extend({
  selector: ".o_digitalizacion_registro_mount",
  start() {
    const props = {
      proyecto_id: this.$el.data("proyecto-id"),
      miembros: this.$el.data("miembros"),
      etapas: this.$el.data("etapas"),
      escaneres: this.$el.data("escaneres"),
    };
    mount(RegistroForm, this.el, { props, env: this.env });
  },
});
