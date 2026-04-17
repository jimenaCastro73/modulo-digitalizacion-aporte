# Gestión de Digitalización — Módulo Odoo 17

> **Módulo desarrollado como Práctica Profesional en OTEC GLOBAL**  
> Autor: Jimena Castro · Versión `17.0.2.0.0` · Licencia LGPL-3

---

## Descripción general

Módulo personalizado para Odoo 17 que permite gestionar proyectos de digitalización de documentos físicos. Proporciona un **backoffice administrativo** para la gerencia/administrador y un **portal web** para que los líderes de equipo registren la producción diaria de sus digitalizadores.

El flujo de trabajo representa el ciclo completo de una caja de documentos:

```
Limpieza → Ordenado → Digitalizado → Editado → Indexado
```

---

## Tabla de contenidos

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Arquitectura del módulo](#arquitectura-del-módulo)
- [Modelos de datos](#modelos-de-datos)
- [Seguridad y permisos](#seguridad-y-permisos)
- [Portal web (Líder)](#portal-web-líder)
- [API REST interna](#api-rest-interna)
- [Vistas de administración](#vistas-de-administración)
- [Validaciones implementadas](#validaciones-implementadas)
- [Reportes PDF](#reportes-pdf)
- [Pruebas automatizadas](#pruebas-automatizadas)
- [Estructura de archivos](#estructura-de-archivos)
- [Entorno Docker](#entorno-docker)

---

## Requisitos

| Componente | Versión mínima |
|-----------|---------------|
| Odoo | 17.0 Community o Enterprise |
| Python | 3.10+ |
| PostgreSQL | 15 |
| Módulos Odoo dependientes | `base`, `contacts`, `website` |

---

## Instalación

### 1. Copiar el módulo

```bash
cp -r addons/digitalizacion /ruta/a/odoo/addons/
```

### 2. Instalar en Odoo

```bash
odoo -c /etc/odoo/odoo.conf -d nombre_db -i digitalizacion
```

### 3. Actualizar módulo existente

```bash
odoo -c /etc/odoo/odoo.conf -d nombre_db -u digitalizacion --stop-after-init
```

### Con Docker (entorno del proyecto)

```bash
# Actualizar módulo
docker exec odoo.17.otecglobal odoo -c /etc/odoo/odoo.conf \
  -d digitalizacion_dev -u digitalizacion --stop-after-init

# Reiniciar el servidor
docker restart odoo.17.otecglobal
```

> El portal está disponible en `http://localhost:8001` tras el reinicio.

---

## Arquitectura del módulo

```
digitalizacion/
├── __manifest__.py              # Metadatos y lista de archivos a cargar
├── __init__.py
│
├── models/                      # Capa ORM — 6 modelos
│   ├── etapa.py                 # T-01 Catálogo de etapas
│   ├── tipo_escaner.py          # T-02 Catálogo de escáneres
│   ├── proyecto.py              # T-03 Proyectos de digitalización
│   ├── asignacion.py            # T-04 Asignación líder↔proyecto
│   ├── miembro_proyecto.py      # T-05 Equipo por proyecto
│   ├── registro.py              # T-06 Registro diario de producción
│   └── mixins.py                # Validadores reutilizables (DRY)
│
├── controllers/
│   └── portal.py                # Rutas HTTP GET/POST del portal
│
├── security/
│   ├── digitalizacion_groups.xml          # Grupos: Admin, Líder
│   ├── digitalizacion_proyecto_security.xml  # Reglas de acceso a proyectos
│   ├── digitalizacion_registro_security.xml  # Reglas de acceso a registros
│   └── ir.model.access.csv               # ACLs por modelo y grupo
│
├── data/
│   └── etapa_data.xml           # Datos iniciales de las 5 etapas
│
├── tools/
│   ├── constantes.py            # Límites, configuración de etapas
│   └── utils.py                 # Funciones puras de validación
│
├── views/
│   ├── admin/                   # Backend (solo Administrador)
│   │   ├── proyectos/
│   │   │   ├── proyecto_views.xml        # Centro de Mando: Dashboard, Equipo, Estadísticas
│   │   │   └── registro_views.xml        # Vistas de registros (form, tree, pivot, graph)
│   │   ├── configuracion/
│   │   │   ├── etapa_views.xml
│   │   │   └── tipo_escaner_views.xml
│   │   ├── dashboard_views.xml  # Dashboard global de análisis
│   │   └── digitalizacion_menus.xml     # Menú principal
│   │
│   └── portal/                  # Frontend (Líder)
│       ├── portal_home_templates.xml             # Dashboard con KPIs
│       ├── portal_proyecto_templates.xml         # Detalle del proyecto
│       ├── portal_registro_form_templates.xml    # Formulario multi-fila (OWL)
│       ├── portal_miembros_templates.xml         # Análisis de equipo + gráficos
│       └── website_menu.xml                      # Integración en navegación web
│
├── report/
│   └── proyecto_report_views.xml # Reporte PDF QWeb
│
├── static/
│   ├── description/
│   │   └── icon.png           # Icono del módulo
│   └── src/
│       └── portal/
│           ├── js/
│           │   └── portal_registro_form.js   # Componente OWL reactivo para el formulario de registros
│           └── css/
│               └── portal_digitalizacion.css # Estilos CSS con variables
│
└── tests/
    ├── test_digitalizacion_v2.py
```

---

## Modelos de datos

### T-01 · `digitalizacion.etapa` — Catálogo de etapas

Catálogo configurable del proceso. Se instalan 5 etapas por defecto (no se sobreescriben en actualizaciones).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre de la etapa (único, no puede ser solo números) |
| `sequence` | Integer | Orden de visualización (≥ 0) |
| `active` | Boolean | Soft delete |

**Etapas instaladas por defecto:**

| Secuencia | Nombre |
|-----------|--------|
| 10 | Limpieza |
| 20 | Digitalizado |
| 30 | Editado |
| 40 | Indexado |
| 50 | Ordenado |

---

### T-02 · `digitalizacion.tipo_escaner` — Catálogo de escáneres

Catálogo global de equipos usados en la etapa Digitalizado.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre/modelo del equipo (único, no puede ser solo números) |
| `description` | Text | Especificaciones adicionales |
| `active` | Boolean | Soft delete |

---

### T-03 · `digitalizacion.proyecto` — Proyectos

Registro central de cada proyecto de digitalización.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre único del proyecto |
| `description` | Text | Descripción (máx. 500 caracteres) |
| `fecha_inicio` | Date | Fecha de inicio (requerida) |
| `fecha_fin_estimada` | Date | Fecha estimada de fin (debe ser ≥ inicio) |
| `duracion_estimada` | Float (compute) | Días entre inicio y fin |
| `state` | Selection | `en_curso` / `pausado` / `finalizado` |
| `active` | Boolean | Soft delete |
| `asignacion_ids` | One2many | Líderes asignados |
| `miembro_ids` | One2many | Equipo del proyecto |
| `registro_ids` | One2many | Registros de trabajo |

**Campos computados:**
- `lider_ids`: Usuarios asignados como líderes activos
- `total_miembros`: Conteo de miembros activos
- `total_registros`: Conteo de registros
- `total_escaneos`: Suma acumulada de escaneos
- `etapa_dominante`: Etapa con mayor producción acumulada

**Constraint SQL:** nombre único por base de datos.

---

### T-04 · `digitalizacion.asignacion` — Asignación Líder ↔ Proyecto

Tabla puente entre un usuario portal (Líder) y un proyecto. **Se crea manualmente** desde el formulario de miembro cuando se marca `es_lider=True`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `lider_id` | Many2one (res.users) | Usuario portal con rol Líder |
| `proyecto_id` | Many2one | Proyecto asignado |
| `fecha_asignacion` | Date | Fecha de asignación (no puede ser futura) |
| `active` | Boolean | Soft delete — controla acceso al portal |

**Constraint SQL:** `UNIQUE(lider_id, proyecto_id)`.

---

### T-05 · `digitalizacion.miembro_proyecto` — Equipo por proyecto

Integrantes del equipo de digitalización. Un mismo contacto puede pertenecer a múltiples proyectos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `proyecto_id` | Many2one | Proyecto al que pertenece |
| `partner_id` | Many2one (res.partner) | Contacto del integrante |
| `fecha_integracion` | Date | Fecha de incorporación |
| `fecha_salida` | Date | Si está informada, excluye al miembro del formulario de registro |
| `es_lider` | Boolean | Marca como líder — sincroniza con T-04 automáticamente |
| `active` | Boolean | Soft delete |

**Campos computados:**
- `total_registros`: Registros de trabajo emitidos

**Constraint SQL:** `UNIQUE(proyecto_id, partner_id)`.  
**Regla de negocio:** Solo puede haber **un líder activo** por proyecto.

**Sincronización con asignaciones:**
- Al marcar `es_lider=True`, crea/reactiva automáticamente la asignación en T-04
- Al desmarcar `es_lider=False`, desactiva la asignación correspondiente
- Al informar `fecha_salida`, desactiva el miembro y limpia el liderazgo

---

### T-06 · `digitalizacion.registro` — Registro diario de producción

Granularidad: 1 registro = 1 miembro + 1 etapa + cantidades del día.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `lider_id` | Many2one (res.users) | Usuario que registró (auto, no modificable) |
| `miembro_id` | Many2one | Digitalizador |
| `proyecto_id` | Many2one | Proyecto |
| `etapa_id` | Many2one | Etapa del proceso |
| `fecha` | Date | Fecha de la producción (no futura) |
| `hora` | Datetime | Timestamp de envío (readonly) |
| `referencia_cajas` | Char | Códigos o descripción de cajas (máx. 200 chars) |
| `no_expedientes` | Integer | Expedientes procesados (0 – 999 999) |
| `total_folios` | Integer | Folios físicos (0 – 999 999) |
| `total_escaneos` | Integer | Imágenes digitales escaneadas (0 – 999 999) |
| `tipo_escaner_ids` | Many2many | Equipos usados (solo etapa Digitalizado) |
| `expedientes_indexados` | Integer | Expedientes indexados (0 – 999 999) |
| `folios_indexados` | Integer | Folios indexados (0 – 999 999) |
| `observacion` | Text | Notas libres (máx. 500 caracteres) |

**Campos computados:**
- `produccion_principal`: Métrica principal según etapa
- `unidad_produccion`: Unidad de la métrica principal

**Campos activos por etapa:**

| Etapa | Campos visibles |
|-------|----------------|
| Limpieza | `referencia_cajas`, `no_expedientes`, `total_folios` |
| Ordenado | `referencia_cajas`, `no_expedientes`, `total_folios` |
| Digitalizado | Limpieza + `total_escaneos`, `tipo_escaner_ids` |
| Editado | `referencia_cajas`, `total_folios` |
| Indexado | `expedientes_indexados`, `folios_indexados` |

**Nota sobre Editado:** A diferencia de versiones anteriores, la etapa Editado ahora usa el campo `total_folios` directamente (igual que Limpieza/Ordenado), sin campos propios. Esto simplifica el modelo y alinea con los datos reales del cliente.

---

## Seguridad y permisos

### Grupos

| Grupo | Hereda de | Acceso |
|-------|-----------|--------|
| **Administrador** | `base.group_user` | Backoffice completo: proyectos, registros, catálogos, dashboard |
| **Líder de equipo** | `base.group_portal` | Solo portal web: registrar producción diaria |

### Permisos por modelo (ACL)

| Modelo | Admin | Líder |
|--------|-------|-------|
| `digitalizacion.etapa` | CRUD | Solo lectura |
| `digitalizacion.tipo_escaner` | CRUD | Solo lectura |
| `digitalizacion.proyecto` | CRUD | Solo lectura |
| `digitalizacion.asignacion` | CRUD | Solo lectura |
| `digitalizacion.miembro_proyecto` | CRUD | Solo lectura |
| `digitalizacion.registro` | CRUD | Crear/Leer/Editar (no eliminar) |

### Reglas de acceso fila a fila (ir.rule)

Se implementan **3 reglas de seguridad** a nivel de registro:

| Regla | Modelo | Dominio | Permisos Líder |
|-------|--------|--------|---|
| `rule_lider_solo_sus_proyectos` | `proyecto` | `asignacion_ids.lider_id = user` | Solo lectura |
| `rule_lider_solo_sus_registros` | `registro` | `proyecto_id.asignacion_ids.lider_id = user` | Crear/Leer/Editar |
| `rule_lider_solo_sus_miembros` | `miembro_proyecto` | `proyecto_id.asignacion_ids.lider_id = user` | Solo lectura |

El líder solo accede a proyectos donde tiene una asignación **activa** con proyecto en estado `activo`.

---

## Portal web (Líder)

El portal está disponible en `/digitalizacion/v1/` y requiere autenticación con rol **Líder de equipo**.

### Rutas GET

| Ruta | Vista | Descripción |
|------|-------|-------------|
| `/digitalizacion/v1/dashboard` | `portal_home_templates.xml` | Dashboard principal con KPIs, resumen por etapa y últimos registros |
| `/digitalizacion/v1/proyectos/<id>` | `portal_proyecto_templates.xml` | Detalle del proyecto, metas globales y accesos operativos |
| `/digitalizacion/v1/proyectos/<id>/form` | `portal_registro_form_templates.xml` | Formulario multi-fila reactivo para registrar producción |
| `/digitalizacion/v1/proyectos/<id>/miembros` | `portal_miembros_templates.xml` | Equipo del proyecto con gráfico de participación por etapa |

### Dashboard — Filtros disponibles

| Parámetro URL | Valores |
|---------------|---------|
| `periodo` | `hoy`, `semana`, `mes` (default), `custom` |
| `fecha_desde` | `YYYY-MM-DD` (con `periodo=custom`) |
| `fecha_hasta` | `YYYY-MM-DD` (con `periodo=custom`) |
| `proyecto_id` | ID del proyecto (si el líder tiene varios asignados) |
| `page` | Número de página para la tabla de últimos registros |

### Formulario de registro — Características

- **Multi-fila OWL:** el líder agrega N filas, una por cada combinación digitalizador + etapa
- **Visibilidad dinámica:** los campos se muestran/ocultan según la etapa seleccionada (JavaScript reactivo)
- **Validación en tiempo real:** errores inline sin recargar la página
- **Bloqueo de fecha futura:** el datepicker tiene `max = fecha_hoy` — no permite seleccionar fechas futuras
- **Límites HTML:** `min="0"` y `max="999999"` en campos numéricos; `maxlength` en campos de texto

### Validaciones en el cliente (JavaScript)

El componente OWL `RegistroForm` implementa validadores puros para sanitización e validación previa al envío:

| Validación | Descripción |
|-----------|-------------|
| **Digitalizador (miembro_id)** | Requerido |
| **Etapa (etapa_id)** | Requerido |
| **Campos numéricos** | 0 ≤ valor ≤ 999 999; entero (no decimales) |
| **Referencia de cajas** | Máx. 200 chars; debe contener al menos 1 alfanumérico |
| **Observación** | Máx. 500 caracteres |
| **Producción mínima** | Al menos 1 campo de producción > 0 según etapa |
| **Escáner (si Digitalizado)** | Obligatorio si `etapa_id = Digitalizado` |

**Ejemplo de reglas por etapa:**

```javascript
// Limpieza y Ordenado
{
  caja: true,
  expedientes: true,
  folios: true,
  escaneos: false,
  escaner: false,
}

// Digitalizado
{
  caja: true,
  expedientes: true,
  folios: true,
  escaneos: true,    // ← Obligatorio
  escaner: true,     // ← Obligatorio
}

// Editado (Simplificado)
{
  caja: true,
  expedientes: false, // ← Ya NO usa no_expedientes
  folios: true,
  escaneos: false,
  escaner: false,
}

// Indexado
{
  caja: false,
  expedientes: false,
  folios: false,
  escaneos: false,
  escaner: false,
  expIndexados: true,
  foliosIndexados: true,
}
```

---

## API REST interna

**Ruta:** `POST /digitalizacion/api/v1/proyectos/<id>/registros`  
**Autenticación:** `auth=user` + CSRF token de Odoo  
**Content-Type:** `application/json`

### Estructura del payload

```json
{
  "jsonrpc": "2.0",
  "params": {
    "fecha": "2026-04-03",
    "registros": [
      {
        "miembro_id": 42,
        "etapa_id": 1,
        "no_expedientes": 15,
        "total_folios": 120,
        "total_escaneos": 0,
        "tipo_escaner_ids": [],
        "expedientes_indexados": 0,
        "folios_indexados": 0,
        "referencia_cajas": "BF202, BF199",
        "observacion": "Sin incidencias"
      }
    ]
  }
}
```

### Respuestas

**Éxito:**
```json
{
  "result": {
    "success": true,
    "ids": [101, 102, 103],
    "total": 3
  }
}
```

**Error de validación:**
```json
{
  "result": {
    "success": false,
    "error": "Descripción del error"
  }
}
```

### Validaciones del controlador

| Validación | Descripción |
|-----------|-------------|
| Formato de fecha | Debe ser `YYYY-MM-DD`, no futura |
| Tipo de `registros` | Debe ser un array, mínimo 1 elemento |
| Límite de filas | Máximo **50 filas** por request |
| `miembro_id` / `etapa_id` | Entero positivo obligatorio |
| Campos numéricos | Entero, entre 0 y 999 999 |
| `referencia_cajas` | String, máx. 200 chars, debe contener al menos 1 alfanumérico |
| `observacion` | String, máx. 500 chars |
| Acceso al proyecto | El líder debe tener asignación activa |

---

## Vistas de administración

Accesibles desde el menú principal **Digitalización** (solo rol Administrador).

### Estructura del menú

| Menú | Descripción |
|------|-------------|
| **Proyectos** | Centro de Mando: gestión unificada de líderes, personal, dashboard y reportes desde un solo formulario |
| **Dashboard** | Análisis global de producción con gráficos (línea, barras, pivot) |
| **Configuración** | Catálogos de etapas y escáneres |

### Vistas específicas

#### Proyectos (Centro de Mando V2)

El formulario de Proyecto es el centro neurálgico y encapsula:

1. **Pestaña Dashboard:**
   - KPIs: Escaneos totales, Registros, Etapa dominante, Duración estimada
   - Botón "ABRIR ANÁLISIS GRÁFICO" para ver líneas de tendencia

2. **Pestaña Miembros de Equipo:**
   - Tabla inline editable con digitalizadores
   - Checkbox para marcar líder del proyecto
   - Cómputo automático de registros por miembro

3. **Pestaña Bitácora:**
   - Vistas de registros (tree, form, pivot, graph)
   - Análisis cruzado de producción por miembro, etapa y fecha

#### Vistas de Registros

- **Tree (lista):** Ordenada por fecha descendente
- **Form:** Con visibilidad dinámica de campos por etapa
- **Pivot:** Análisis cruzado (Proyecto × Miembro × Etapa)
- **Graph:** Tendencia diaria de producción (línea)

#### Dashboard global

Accesible desde menú. Ofrece:
- **Graph (Línea):** Tendencia diaria de escaneos
- **Graph (Barras):** Producción por digitalizador
- **Pivot:** Análisis cruzado de todos los proyectos
- Filtros por proyecto, etapa, fecha

#### Kanban de Proyectos

Vista de tarjetas agrupadas por estado (`en_curso`, `pausado`, `finalizado`) con:
- Badges de estado
- KPIs resumidos
- Acciones rápidas (abrir formulario, ver registros)

---

## Reportes PDF

### Reporte de Proyecto

**Acción:** Disponible desde el botón "Imprimir Reporte" en el formulario del Proyecto

**Contenido:**
- Cabecera con nombre del proyecto y estado (verde = en curso, ámbar = pausa, azul = finalizado)
- Matriz de 4 KPIs: Integrantes, Escaneos, Producciones, Días Estimados
- Configuración del proyecto: Fechas, Líderes de Operación
- Desglose de producción acumulada por etapa (tabla)
- Equipo de trabajo asignado con roles (Líder ★ vs Digitalizador)
- Pie de página con metadatos

**Estilo:** Inspirado en el portal del líder con branding corporativo (rojo #af1714), variables CSS y responsivo para impresión

---

## Validaciones implementadas

### Nivel Python (`@api.constrains`)

| Modelo | Constraint | Regla |
|--------|-----------|-------|
| `etapa` | `_check_name` | Nombre no vacío, no solo dígitos (heredado de mixin) |
| `etapa` | `_check_sequence` | Secuencia ≥ 0 |
| `tipo_escaner` | `_check_name` | Nombre no vacío, no solo dígitos (heredado de mixin) |
| `proyecto` | `_check_name` | Nombre no vacío, no solo dígitos |
| `proyecto` | `_check_fechas` | `fecha_fin ≥ fecha_inicio` |
| `proyecto` | `_check_description_longitud` | Descripción ≤ 500 caracteres |
| `asignacion` | `_check_lider_tiene_grupo` | El usuario pertenece al grupo Líder |
| `asignacion` | `_check_fecha_asignacion` | Fecha de asignación no futura |
| `miembro_proyecto` | `_check_fechas` | `fecha_salida ≥ fecha_integracion` |
| `miembro_proyecto` | `_check_lider_unico` | Solo 1 líder activo por proyecto |
| `registro` | `_check_fecha_no_futura` | `fecha ≤ hoy` |
| `registro` | `_check_valores_positivos` | Todos los campos numéricos: `0 ≤ valor ≤ 999 999` |
| `registro` | `_check_campos_minimos_por_etapa` | Cada etapa exige al menos 1 campo de producción > 0 |
| `registro` | `_check_miembro_activo` | El digitalizador no debe tener fecha de salida |
| `registro` | `_check_miembro_pertenece_proyecto` | El digitalizador pertenece al proyecto |
| `registro` | `_check_referencia_cajas` | No vacía (si aplica), contiene al menos 1 carácter alfanumérico |
| `registro` | `_check_observacion_longitud` | Observación ≤ 500 caracteres |

### Nivel SQL (`_sql_constraints`)

| Modelo | Constraint |
|--------|-----------|
| `etapa` | `UNIQUE(name)` |
| `tipo_escaner` | `UNIQUE(name)` |
| `proyecto` | `UNIQUE(name)` |
| `asignacion` | `UNIQUE(lider_id, proyecto_id)` |
| `miembro_proyecto` | `UNIQUE(proyecto_id, partner_id)` |

### Nivel HTML/JavaScript (Portal)

- `<input type="number">` con `min="0"` y `max="999999"`
- `<input type="text">` con `maxlength` correspondiente (200 para cajas, 500 para observación)
- `<input type="date">` con `max` = fecha actual (vía JavaScript)
- Validación reactiva en tiempo real con OWL
- Mensajes de error inline contextualizados por campo

---

## Arquitectura DRY (Don't Repeat Yourself)

El módulo implementa principios DRY en varios niveles:

### 1. **Constantes centralizadas (`tools/constantes.py`)**

Todos los límites, configuración de etapas y mensajes se definen en un único lugar:

```python
MAX_FILAS = 50
MAX_CAMPO_NUMERICO = 999_999
MAX_LEN_TEXTO_CORTO = 200
MAX_LEN_TEXTO_LARGO = 500

ETAPAS_CONFIG = {
    "Limpieza": {
        "campo_principal": "no_expedientes",
        "unidad": "expedientes",
        "campos_minimos": ["no_expedientes", "total_folios"],
    },
    # ... resto de etapas
}
```

### 2. **Validadores puros (`tools/utils.py`)**

Funciones sin estado ORM, reutilizables desde controladores, modelos o tests:

```python
sanitizar_entero(valor, nombre_campo, min_val, max_val)
validar_id_positivo(valor, nombre_campo, prefijo)
sanitizar_texto(valor, nombre_campo, max_len)
sanitizar_referencia_cajas(valor, prefijo)
```

### 3. **Mixin de validación (`models/mixins.py`)**

La validación `_check_name` se hereda en 3 modelos (`etapa`, `tipo_escaner`, `proyecto`):

```python
class _NombreValidoMixin(models.AbstractModel):
    @api.constrains("name")
    def _check_name(self):
        # Lógica única, heredada por 3 modelos
```

### 4. **Métodos del modelo como API (`models/registro.py`)**

La lógica de validación, API y KPIs vive en el modelo, donde debe estar:

```python
@api.model
def validar_fila_api(self, fila, idx):
    # Valida y normaliza datos del portal

@api.model
def get_kpis_lider(self, lider_id, domain_extra=None):
    # Calcula KPIs usados por templates

@api.model
def get_participacion_equipo(self, proyecto_id):
    # Datos para gráficos sin duplicar lógica
```

### 5. **Componente OWL modular (`static/src/portal/js/portal_registro_form.js`)**

Clases puras para validación, gestión de filas y API:

```javascript
class ValidadorFila { ... }    // Reutilizable
class GestorFila { ... }       // Reutilizable
class ServicioApi { ... }      // Reutilizable

export class RegistroForm extends Component { ... }  // Orquestador
```

**Beneficio:** Cambiar un límite o regla de etapa actualiza automáticamente:
- Validaciones Python (modelo)
- Validaciones JavaScript (portal)
- Reportes
- Templates

---

## Pruebas automatizadas

### Ejecutar toda la suite

```bash
docker exec odoo.17.otecglobal odoo \
  -c /etc/odoo/odoo.conf \
  -d digitalizacion_dev \
  --test-enable \
  --stop-after-init \
  --test-tags "/digitalizacion"
```

### Suite de pruebas — 70 casos en total

| Archivo | Clase | Tests | Tipo | Cobertura |
|---------|-------|-------|------|-----------|
| `test_registro_unitario.py` | `TestRegistroUnitario` | 28 | Caja blanca | CB-01 a CB-10: validaciones, cómputos, overrides |
| `test_registro_regresion.py` | `TestRegistroRegresion` | 12 | Caja negra | CN-01 a CN-10: flujos completos CRUD, regresión |
| `test_proyecto_unitario.py` | `TestProyectoUnitario` | 14 | Caja blanca | PY-01 a PY-07: fechas, constraints, computados |
| `test_miembro_unitario.py` | `TestMiembroUnitario` | 13 | Caja blanca | MP-01 a MP-07: liderazgo, salida, sincronización |

**Resultado esperado:**

```
0 failed, 0 error(s) of 70 tests
```

---

## Estructura de archivos

```
modulo-digitalizacion-aporte/
├── addons/
│   └── digitalizacion/
│       ├── __manifest__.py
│       ├── __init__.py
│       ├── controllers/
│       │   ├── __init__.py
│       │   └── portal.py
│       ├── data/
│       │   └── etapa_data.xml
│       ├── models/
│       │   ├── __init__.py
│       │   ├── asignacion.py
│       │   ├── etapa.py
│       │   ├── miembro_proyecto.py
│       │   ├── mixins.py
│       │   ├── proyecto.py
│       │   ├── registro.py
│       │   └── tipo_escaner.py
│       ├── report/
│       │   └── proyecto_report_views.xml
│       ├── security/
│       │   ├── digitalizacion_groups.xml
│       │   ├── digitalizacion_proyecto_security.xml
│       │   ├── digitalizacion_registro_security.xml
│       │   └── ir.model.access.csv
│       ├── static/
│       │   ├── description/
│       │   │   └── icon.png
│       │   └── src/
│       │       └── portal/
│       │           ├── js/
│       │           │   └── portal_registro_form.js
│       │           └── css/
│       │               └── portal_digitalizacion.css
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── test_miembro_unitario.py
│       │   ├── test_proyecto_unitario.py
│       │   ├── test_registro_regresion.py
│       │   └── test_registro_unitario.py
│       ├── tools/
│       │   ├── constantes.py
│       │   └── utils.py
│       └── views/
│           ├── admin/
│           │   ├── configuracion/
│           │   │   ├── etapa_views.xml
│           │   │   └── tipo_escaner_views.xml
│           │   ├── dashboard_views.xml
│           │   ├── digitalizacion_menus.xml
│           │   └── proyectos/
│           │       ├── proyecto_views.xml
│           │       └── registro_views.xml
│           └── portal/
│               ├── portal_home_templates.xml
│               ├── portal_miembros_templates.xml
│               ├── portal_proyecto_templates.xml
│               ├── portal_registro_form_templates.xml
│               └── website_menu.xml
├── docker-compose.yaml
├── config/
│   └── odoo.conf
└── README.md
```

---

## Entorno Docker

El proyecto incluye un entorno Docker con dos contenedores:

| Contenedor | Imagen | Puerto |
|-----------|--------|--------|
| `odoo.17.otecglobal` | Odoo 17 | `8001` (HTTP), `8002` (longpolling) |
| `postgres.db.otec` | PostgreSQL 15 | `5432` |

### Comandos útiles

```bash
# Estado de los contenedores
docker ps

# Logs de Odoo en tiempo real
docker logs -f odoo.17.otecglobal

# Actualizar módulo
docker exec odoo.17.otecglobal odoo \
  -c /etc/odoo/odoo.conf \
  -d digitalizacion_dev \
  -u digitalizacion \
  --stop-after-init

# Acceder a la shell de Odoo
docker exec -it odoo.17.otecglobal odoo shell \
  -c /etc/odoo/odoo.conf \
  -d digitalizacion_dev

# Reiniciar servidor
docker restart odoo.17.otecglobal
```

---

## Notas de desarrollo

- **Odoo 17 — sintaxis de vistas:** Se usan expresiones Python directas en `invisible=""` en lugar del objeto `attrs={}` deprecado.
- **QWeb — operadores en XML:** Los operadores `>`, `>=`, `<`, `<=` dentro de atributos `t-if` o bloques `<script>` **deben escaparse** (`&gt;`, `&lt;`).
- **Framework OWL (Odoo Web Library):** El formulario de registro ha sido modernizado utilizando OWL, el framework reactivo de Odoo. Esto permite una gestión dinámica de múltiples filas, estados reactivos para la visibilidad de campos por etapa y validaciones en tiempo real sin recargar la página.
- **Portal — fetch nativo:** El componente OWL utiliza `fetch()` nativo con CSRF token de Odoo para comunicarse con la API, eliminando dependencias de métodos legacy.
- **Iconos — FontAwesome 6:** En Odoo 17 se deben utilizar las clases `fa-solid` (para FA 6) y etiquetas de cierre explícito `</i>` para garantizar el renderizado correcto en el portal.
- **CSS Variables:** El portal utiliza variables CSS personalizadas (`:root { --dig-primary, --dig-bg, etc. }`) para consistencia visual y mantenimiento centralizado.
- **Gráficos sin librerías pesadas:** Los gráficos de barras apiladas y heatmaps se implementan con CSS Flexbox puro (sin Chart.js o similares), optimizando carga y rendimiento.
- **lider_id en registros:** El campo `lider_id` se asigna automáticamente en `create()` al usuario en sesión y no puede modificarse mediante `write()`.
- **Arquitectura de Vistas V2 (Centralizado):** Se eliminaron los menús redundantes de Miembros, Asignaciones y Registros. Ahora todo el control operativo se realiza desde el formulario del Proyecto, filtrando automáticamente la información relacionada para mejorar la experiencia de usuario (UX) y evitar errores de contexto.
- **Principio DRY — Constantes:** Todos los límites numéricos y configuración de etapas residen en `tools/constantes.py`, evitando duplicación entre Python, JavaScript y reportes.
- **Principio DRY — Validadores:** Las funciones de sanitización viven en `tools/utils.py` (funciones puras sin ORM) para reutilización desde controladores, modelos y tests.
- **Reportes:** Se implementó un motor de reportes PDF que hereda los estilos visuales del dashboard del portal, proporcionando un documento ejecutivo con branding corporativo y métricas limpias para la gerencia.

---

## Cambios recientes (vs. versiones anteriores)

### Simplificaciones en el modelo de datos

1. **Etapa Editado:** Ahora usa `total_folios` directamente (reutiliza campo de Limpieza/Ordenado) en lugar de campos propios `expedientes_editados` y `folios_editados`. Esto se alinea con los datos reales del cliente.

2. **Asignaciones:** Ya **no crean automáticamente** `miembro_proyecto`. La creación de miembros es ahora manual desde el backoffice, simplificando la lógica de sincronización.

3. **Límites de observación:** Actualizado a **500 caracteres máximo** (antes era documentado como 2000, pero el código siempre fue 500).

### Mejoras arquitectónicas

1. **Componente OWL reactivo:** Reemplaza el anterior formulario HTML con validación dual cliente/servidor.

2. **Métodos de API en modelos:** `validar_fila_api()`, `get_kpis_lider()`, `get_participacion_equipo()` se encapsulan en el modelo donde pertenecen, no en el controlador.

3. **Gráficos sin Chart.js:** Barras apiladas con CSS Flexbox puro, heatmaps con etiquetas HTML dinámicas.

4. **Variables CSS centralizadas:** Portal y reportes PDF usan variables de root (`:root { --dig-primary, ... }`) para consistencia.

---

*Desarrollado como aporte de la Práctica Profesional · OTEC GLOBAL · Febrero-Abril 2026*