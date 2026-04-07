/** @odoo-module **/

import { Component, useState, xml, mount } from "@odoo/owl";
import publicWidget from "@web/legacy/js/public/public_widget";

const REGLAS_ETAPA = {
  limpieza: { caja: true, expedientes: true, folios: true, escaneos: false, escaner: false, expEditados: false, foliosEditados: false, expIndexados: false, foliosIndexados: false },
  ordenado: { caja: true, expedientes: true, folios: true, escaneos: false, escaner: false, expEditados: false, foliosEditados: false, expIndexados: false, foliosIndexados: false },
  digitalizado: { caja: true, expedientes: true, folios: true, escaneos: true, escaner: true, expEditados: false, foliosEditados: false, expIndexados: false, foliosIndexados: false },
  editado: { caja: false, expedientes: false, folios: false, escaneos: false, escaner: false, expEditados: true, foliosEditados: true, expIndexados: false, foliosIndexados: false },
  indexado: { caja: false, expedientes: false, folios: false, escaneos: false, escaner: false, expEditados: false, foliosEditados: false, expIndexados: true, foliosIndexados: true },
};

const REGLA_DEFAULT = { caja: true, expedientes: true, folios: true, escaneos: false, escaner: false, expEditados: false, foliosEditados: false, expIndexados: false, foliosIndexados: false };

export class RegistroForm extends Component {
  static template = xml`
    <div class="o_digitalizacion_form_wrapper mt-3">
        <!-- Alertas dinámicas -->
        <div t-if="state.alerta" t-attf-class="alert alert-{{ state.alerta.tipo }} alert-dismissible shadow-sm border-0 fade show mb-4 rounded-3 p-3 d-flex align-items-center" role="alert">
            <i t-attf-class="fa {{ state.alerta.tipo == 'success' ? 'fa-check-circle' : 'fa-exclamation-circle' }} me-3 fa-lg opacity-75"/>
            <div class="flex-grow-1 fw-semibold text-break"><t t-esc="state.alerta.mensaje"/></div>
            <button t-on-click="() => this.state.alerta = null" type="button" class="btn-close shadow-none" aria-label="Close"/>
        </div>

        <div class="card border-0 bg-transparent">
            <!-- Jumbotron de Producción -->
            <div class="d-flex flex-column flex-md-row align-items-md-end justify-content-between mb-4 gap-3 bg-white p-4 rounded-4 shadow-sm border border-light">
                <div>
                   <h2 class="h4 mb-1 fw-bold text-dark text-uppercase tracking-tight">Registro de Producción Diaria</h2>
                   <p class="text-muted small mb-0 fw-medium">Reporte de avance y métricas de digitalización de documentos.</p>
                </div>
                <div class="d-flex align-items-center gap-3">
                    <label class="small fw-bold text-dark text-uppercase mb-0 opacity-75">Fecha reportada:</label>
                    <input t-att-max="this._getToday()" t-model="state.fecha" type="date" class="form-control form-control-sm border-light shadow-none bg-light p-2 ps-3 fw-bold rounded-3" style="width: 170px;"/>
                </div>
            </div>

            <!-- Listado de Fals por Producción -->
            <div class="o_digitalizacion_cards_list">
                <t t-foreach="state.filas" t-as="fila" t-key="fila.id">
                    <t t-set="reglas" t-value="this.getVisibleColumns(fila.etapa_id)"/>
                    <div class="card o_digitalizacion_record_card mb-4" t-attf-style="border-left: 5px solid {{ fila.etapa_id ? 'var(--dig-primary)' : '#e5e7eb' }} !important;">
                        <div class="card-header d-flex justify-content-between align-items-center py-3 border-0 bg-white">
                            <div class="d-flex align-items-center flex-wrap gap-3 flex-grow-1">
                                <div class="input-group input-group-sm w-auto shadow-sm rounded-3 overflow-hidden border border-light">
                                    <span class="input-group-text border-0 bg-white text-muted px-3 small fw-bold text-uppercase">Digitalizador</span>
                                    <select t-model.number="fila.miembro_id" class="form-select border-0 px-2 pe-4 fw-bold text-dark">
                                        <option value="">Seleccionar integrante del equipo...</option>
                                        <t t-foreach="props.miembros" t-as="m" t-key="m.id">
                                            <option t-att-value="m.id" t-esc="m.name"/>
                                        </t>
                                    </select>
                                </div>
                                <div class="input-group input-group-sm w-auto shadow-sm rounded-3 overflow-hidden border border-light">
                                    <span t-attf-class="input-group-text border-0 text-white px-3 fw-bold small text-uppercase {{ fila.etapa_id ? 'bg-primary' : 'bg-secondary opacity-50' }}">Etapa</span>
                                    <select t-model.number="fila.etapa_id" t-on-change="() => this.onEtapaChange(fila)" t-attf-class="form-select border-0 px-2 pe-4 fw-bold {{ fila.etapa_id ? 'text-primary' : 'text-muted' }}">
                                        <option value="">— Elegir etapa actual —</option>
                                        <t t-foreach="props.etapas" t-as="e" t-key="e.id">
                                            <option t-att-value="e.id" t-esc="e.name"/>
                                        </t>
                                    </select>
                                </div>
                            </div>
                            <button t-on-click="() => this.removeRow(fila.id)" type="button" class="btn btn-sm btn-link text-danger border-0 p-2 opacity-50-hover"><i class="fa fa-trash-o fa-lg"/></button>
                        </div>

                        <div class="card-body bg-white pt-1">
                            <div class="row g-4 pt-1">
                                
                                <!-- Sección: Recolección y Carga de Cajas -->
                                <t t-if="reglas.caja or reglas.expedientes or reglas.folios or reglas.escaneos">
                                    <div class="col-12 col-md-6 border-end-md border-light">
                                        <div class="o_digitalizacion_section_label">Recolección de Archivos</div>
                                        <div class="row g-3">
                                            <div t-if="reglas.caja" class="col-12">
                                                <div class="input-group input-group-sm">
                                                    <span class="input-group-text bg-light border-light text-muted small px-3">REFERENCIA:</span>
                                                    <input t-model="fila.referencia_cajas" type="text" class="form-control border-light shadow-none bg-light fw-medium" placeholder="Referencia de cajas procesadas…"/>
                                                </div>
                                            </div>
                                            <div t-if="reglas.expedientes" class="col-6">
                                                <label class="text-muted small fw-bold mb-1 d-block pe-none">Cantidad de expedientes</label>
                                                <input t-model.number="fila.no_expedientes" type="number" class="form-control border-light shadow-none bg-light p-2 text-center" placeholder="0"/>
                                            </div>
                                            <div t-if="reglas.folios" class="col-6">
                                                <label class="text-muted small fw-bold mb-1 d-block pe-none">Cantidad de folios</label>
                                                <input t-model.number="fila.total_folios" type="number" class="form-control border-light shadow-none bg-light p-2 text-center" placeholder="0"/>
                                            </div>
                                            <div t-if="reglas.escaneos" class="col-12 mt-2">
                                                <div class="bg-light p-3 rounded-4 text-center border border-light shadow-sm">
                                                    <span class="text-primary small fw-bold text-uppercase d-block mb-1">Número de escaneos realizados</span>
                                                    <input t-model.number="fila.total_escaneos" type="number" class="form-control form-control-lg border-0 bg-transparent text-center text-primary fw-bold shadow-none p-0" placeholder="0"/>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </t>

                                <!-- Sección: Post-Procesamiento -->
                                <t t-if="reglas.expEditados or reglas.foliosEditados or reglas.expIndexados or reglas.foliosIndexados">
                                    <div class="col-12 col-md-6">
                                        <div class="o_digitalizacion_section_label text-primary text-opacity-75">Control de Calidad e Indexación</div>
                                        <div class="row g-3">
                                            <div t-if="reglas.expEditados" class="col-6">
                                                <label class="text-muted small fw-bold mb-1 d-block pe-none">Expedientes editados</label>
                                                <input t-model.number="fila.expedientes_editados" type="number" class="form-control border-light shadow-none bg-light p-2 text-center" placeholder="0"/>
                                            </div>
                                            <div t-if="reglas.foliosEditados" class="col-6">
                                                <label class="text-muted small fw-bold mb-1 d-block pe-none">Folios editados</label>
                                                <input t-model.number="fila.folios_editados" type="number" class="form-control border-light shadow-none bg-light p-2 text-center" placeholder="0"/>
                                            </div>
                                            <div t-if="reglas.expIndexados" class="col-6">
                                                <label class="text-primary-emphasis small fw-bold mb-1 d-block pe-none">Expedientes indexados</label>
                                                <input t-model.number="fila.expedientes_indexados" type="number" class="form-control border-light shadow-none bg-light p-2 text-center" placeholder="0"/>
                                            </div>
                                            <div t-if="reglas.foliosIndexados" class="col-6">
                                                <label class="text-primary-emphasis small fw-bold mb-1 d-block pe-none">Folios indexados</label>
                                                <input t-model.number="fila.folios_indexados" type="number" class="form-control border-light shadow-none bg-light p-2 text-center" placeholder="0"/>
                                            </div>
                                        </div>
                                    </div>
                                </t>

                                <!-- Herramientas -->
                                <div t-if="reglas.escaner" class="col-12 mt-4 pt-3 border-top border-light border-opacity-50">
                                    <div class="o_digitalizacion_section_label">Equipos de Escaneo Utilizados</div>
                                    <div class="d-flex flex-wrap gap-2 py-1">
                                        <t t-foreach="props.escaneres" t-as="escaner" t-key="escaner.id">
                                            <label class="o_digitalizacion_escaner_chip mb-0 m-1">
                                                <input type="checkbox" class="d-none" t-att-checked="(fila.tipo_escaner_ids || []).includes(escaner.id)" t-on-change="(ev) => this.onEscanerToggle(fila, escaner.id, ev.target.checked)"/>
                                                <span class="fw-bold fs-small"><i t-attf-class="fa fa-hdd-o me-2" /> <t t-esc="escaner.name"/></span>
                                            </label>
                                        </t>
                                    </div>
                                </div>

                                <div class="col-12 mt-4">
                                    <div class="rounded-3 bg-light p-1 px-3 d-flex align-items-center border border-light">
                                       <i class="fa fa-commenting-o text-muted me-2 opacity-75 small"/>
                                       <input t-model="fila.observacion" type="text" class="form-control form-control-sm border-0 bg-transparent shadow-none small fw-medium text-dark" placeholder="Opcional: Indicar observaciones o incidencias de la producción…"/>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </t>
            </div>

            <!-- Footer fijo -->
            <div t-if="state.filas.length > 0" class="d-flex flex-column flex-md-row gap-3 justify-content-between align-items-center mt-4 bg-white p-4 rounded-4 shadow-sm border border-light">
                <button t-on-click="this.addRow" type="button" class="btn btn-outline-primary px-4 py-2 fw-bold w-100 w-md-auto shadow-none">
                    <i class="fa fa-plus-circle me-1"/> Agregar otro registro de producción
                </button>
                <div class="d-flex align-items-center gap-3 w-100 w-md-auto">
                    <span class="text-muted small fw-bold text-uppercase d-none d-md-inline" t-if="!state.isSaving">-</span>
                    <button t-att-disabled="state.isSaving" t-on-click="this.save" type="button" class="btn btn-primary shadow-sm px-5 py-2 btn-lg flex-grow-1 border-0">
                        <i t-attf-class="fa {{ state.isSaving ? 'fa-spinner fa-spin' : 'fa-check' }} me-2"/>
                        <t t-esc="state.isSaving ? 'Guardando...' : 'Confirmar y Guardar Producción'"/>
                    </button>
                </div>
            </div>
        </div>
    </div>
  `;

  setup() {
    this.nextId = 1;
    this.state = useState({ fecha: this._getToday(), filas: [this._createEmptyRow()], alerta: null, isSaving: false });
  }

  _getToday() {
    const hoy = new Date();
    const offset = hoy.getTimezoneOffset();
    const local = new Date(hoy.getTime() - offset * 60 * 1000);
    return local.toISOString().split("T")[0];
  }

  _createEmptyRow() {
    return { id: this.nextId++, miembro_id: "", etapa_id: "", referencia_cajas: "", no_expedientes: 0, total_folios: 0, total_escaneos: 0, tipo_escaner_ids: [], expedientes_editados: 0, folios_editados: 0, expedientes_indexados: 0, folios_indexados: 0, observacion: "" };
  }

  getVisibleColumns(etapaId) {
    if (!etapaId) return REGLA_DEFAULT;
    const etapa = this.props.etapas.find((e) => e.id === etapaId);
    return REGLAS_ETAPA[etapa?.name?.toLowerCase()] || REGLA_DEFAULT;
  }

  onEtapaChange(fila) {
    const reglas = this.getVisibleColumns(fila.etapa_id);
    if (!reglas.caja) fila.referencia_cajas = "";
    if (!reglas.expedientes) fila.no_expedientes = 0;
    if (!reglas.folios) fila.total_folios = 0;
    if (!reglas.escaneos) fila.total_escaneos = 0;
    if (!reglas.escaner) fila.tipo_escaner_ids = [];
    if (!reglas.expEditados) fila.expedientes_editados = 0;
    if (!reglas.foliosEditados) fila.folios_editados = 0;
    if (!reglas.expIndexados) fila.expedientes_indexados = 0;
    if (!reglas.foliosIndexados) fila.folios_indexados = 0;
  }

  onEscanerToggle(fila, escanerId, checked) {
    if (!Array.isArray(fila.tipo_escaner_ids)) fila.tipo_escaner_ids = [];
    const id = Number(escanerId);
    if (checked) {
      if (!fila.tipo_escaner_ids.includes(id)) fila.tipo_escaner_ids = [...fila.tipo_escaner_ids, id];
    } else {
      fila.tipo_escaner_ids = fila.tipo_escaner_ids.filter((v) => v !== id);
    }
  }

  addRow() { this.state.filas.push(this._createEmptyRow()); }
  removeRow(id) { this.state.filas = this.state.filas.filter((fila) => fila.id !== id); }

  extraerMensajeError(errorData) {
    if (errorData.result?.error) return errorData.result.error.message;
    if (errorData.error) return errorData.error.message || "Error del servidor";
    return "Error desconocido.";
  }

  async save() {
    if (!this.state.fecha || this.state.filas.length === 0) return;

    for (const [index, fila] of this.state.filas.entries()) {
        const produccion = (fila.no_expedientes || 0) + (fila.total_folios || 0) + (fila.total_escaneos || 0) + 
                           (fila.expedientes_editados || 0) + (fila.folios_editados || 0) + 
                           (fila.expedientes_indexados || 0) + (fila.folios_indexados || 0);
        
        if (!fila.miembro_id || !fila.etapa_id) {
            this.state.alerta = { tipo: "warning", mensaje: `Debe asignar un digitalizador y una etapa en la línea ${index + 1}.` };
            return;
        }

        if (produccion <= 0) {
            this.state.alerta = { tipo: "warning", mensaje: `La línea ${index + 1} no tiene cantidades de producción reportadas. No se permiten registros en cero.` };
            return;
        }
    }

    this.state.isSaving = true;
    this.state.alerta = null;
    try {
      const respuesta = await fetch(`/digitalizacion/api/v1/proyectos/${this.props.proyecto_id}/registros`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": this._getCookie("csrf_token") },
        body: JSON.stringify({ jsonrpc: "2.0", params: { fecha: this.state.fecha, filas: this.state.filas } }),
      });
      const data = await respuesta.json();
      if (data.result?.success) {
        this.state.alerta = { tipo: "success", mensaje: "¡Producción guardada correctamente!" };
        this.state.filas = [this._createEmptyRow()];
      } else {
        this.state.alerta = { tipo: "danger", mensaje: this.extraerMensajeError(data) };
      }
    } catch {
      this.state.alerta = { tipo: "danger", mensaje: "Error de conexión." };
    } finally { this.state.isSaving = false; }
  }

  _getCookie(name) {
    const parts = `; ${document.cookie}`.split(`; ${name}=`);
    return parts.length === 2 ? parts.pop().split(";").shift() : "";
  }
}

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
