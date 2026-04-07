# Gestión de Digitalización — Módulo Odoo 17

> **Módulo desarrollado como Práctica Profesional en OTEC GLOBAL**  
> Autor: Jimena Castro · Versión `17.0.1.0.0` · Licencia LGPL-3

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
│   └── registro.py              # T-06 Registro diario de producción
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
├── views/
│   ├── admin/                   # Backend (solo Admin)
│   │   ├── proyectos/
│   │   ├── operaciones/
│   │   ├── configuracion/
│   │   ├── dashboard_views.xml
│   │   └── digitalizacion_menus.xml
│   └── portal/                  # Frontend (Líder)
│       ├── portal_home_templates.xml
│       ├── portal_proyecto_templates.xml
│       ├── portal_registro_form_templates.xml
│       └── portal_miembros_templates.xml
│
└── tests/                       # Suite de pruebas
    ├── test_registro_unitario.py
    ├── test_registro_regresion.py
    ├── test_proyecto_unitario.py
    └── test_miembro_unitario.py
```

---

## Modelos de datos

### T-01 · `digitalizacion.etapa` — Catálogo de etapas

Catálogo configurable del proceso. Se instalan 5 etapas por defecto con `noupdate="1"` (no se sobreescriben en actualizaciones).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre de la etapa (único, no puede ser solo números) |
| `sequence` | Integer | Orden de visualización (≥ 0) |
| `active` | Boolean | Soft delete |
| `registro_count` | Integer (compute) | Registros asociados |

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
| `registro_count` | Integer (compute) | Veces usado en registros |

---

### T-03 · `digitalizacion.proyecto` — Proyectos

Registro central de cada proyecto de digitalización.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre único del proyecto |
| `description` | Text | Descripción (máx. 5 000 caracteres) |
| `fecha_inicio` | Date | Fecha de inicio (requerida) |
| `fecha_fin_estimada` | Date | Fecha estimada de fin (debe ser ≥ inicio) |
| `duracion_estimada` | Integer (compute) | Días entre inicio y fin |
| `state` | Selection | `activo` / `inactivo` |
| `active` | Boolean | Soft delete |
| `meta_escaneos` | Integer | Objetivo en número de escaneos (0 a 100 000 000) |
| `progreso` | Float (compute) | Porcentaje de avance respecto a la meta |
| `asignacion_ids` | One2many | Líderes asignados |
| `miembro_ids` | One2many | Equipo del proyecto |
| `registro_ids` | One2many | Registros de trabajo |

**Constraint SQL:** nombre único por base de datos.

---

### T-04 · `digitalizacion.asignacion` — Asignación Líder ↔ Proyecto

Tabla puente entre un usuario portal (Líder) y un proyecto. **Se crea automáticamente** al marcar `es_lider=True` en el miembro correspondiente.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `lider_id` | Many2one (res.users) | Usuario portal con rol Líder |
| `proyecto_id` | Many2one | Proyecto asignado |
| `fecha_asignacion` | Date | Fecha de asignación (no puede ser futura) |
| `active` | Boolean | Soft delete — controla acceso al portal |

**Constraint SQL:** `UNIQUE(lider_id, proyecto_id)`.

> Al crear una asignación, el sistema crea automáticamente el `miembro_proyecto` correspondiente si no existe.

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
| `total_registros` | Integer (compute) | Registros de trabajo emitidos |

**Constraint SQL:** `UNIQUE(proyecto_id, partner_id)`.  
**Regla de negocio:** Solo puede haber **un líder activo** por proyecto.

---

### T-06 · `digitalizacion.registro` — Registro diario de producción

Granularidad: 1 registro = 1 miembro + 1 etapa + cantidades del día.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `lider_id` | Many2one (res.users) | Usuario que registró (auto, no modificable) |
| `miembro_id` | Many2one | Digitalizador |
| `proyecto_id` | Many2one | Proyecto |
| `etapa_id` | Many2one | Etapa del proceso |
| `fecha` | Date | Fecha de la jornada (no futura) |
| `hora` | Datetime | Timestamp de envío (readonly) |
| `referencia_cajas` | Char | Códigos o descripción de cajas (máx. 200 chars) |
| `no_expedientes` | Integer | Expedientes procesados (0 – 999 999) |
| `total_folios` | Integer | Folios físicos (0 – 999 999) |
| `total_escaneos` | Integer | Imágenes digitales escaneadas (0 – 999 999) |
| `tipo_escaner_ids` | Many2many | Equipos usados (solo etapa Digitalizado) |
| `expedientes_editados` | Integer | Expedientes editados (0 – 999 999) |
| `folios_editados` | Integer | Folios editados (0 – 999 999) |
| `expedientes_indexados` | Integer | Expedientes indexados (0 – 999 999) |
| `folios_indexados` | Integer | Folios indexados (0 – 999 999) |
| `observacion` | Text | Notas libres (máx. 2 000 caracteres) |
| `produccion_principal` | Integer (compute) | Métrica principal según etapa |
| `unidad_produccion` | Char (compute) | Unidad de la métrica principal |

**Campos activos por etapa:**

| Etapa | Campos visibles |
|-------|----------------|
| Limpieza / Ordenado | `referencia_cajas`, `no_expedientes`, `total_folios` |
| Digitalizado | Lo anterior + `total_escaneos`, `tipo_escaner_ids` |
| Editado | `expedientes_editados`, `folios_editados` |
| Indexado | `expedientes_indexados`, `folios_indexados` |

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

### Reglas de acceso fila a fila (record rules)

- **Líder → Proyectos:** Solo ve proyectos donde tiene asignación activa con estado `activo`.
- **Líder → Registros:** Solo ve/edita los registros creados por él mismo (`lider_id = uid`).

---

## Portal web (Líder)

El portal está disponible en `/digitalizacion/v1/` y requiere autenticación con rol **Líder de equipo**.

### Rutas GET

| Ruta | Vista | Descripción |
|------|-------|-------------|
| `/digitalizacion/v1/dashboard` | `portal_home_templates.xml` | Dashboard principal con KPIs, resumen por etapa y últimos registros |
| `/digitalizacion/v1/proyectos/<id>` | `portal_proyecto_templates.xml` | Detalle del proyecto: progreso, meta y accesos rápidos |
| `/digitalizacion/v1/proyectos/<id>/form` | `portal_registro_form_templates.xml` | Formulario multi-fila para registrar producción |
| `/digitalizacion/v1/proyectos/<id>/miembros` | `portal_miembros_templates.xml` | Equipo del proyecto con gráfico de participación |

### Dashboard — Filtros disponibles

| Parámetro URL | Valores |
|---------------|---------|
| `periodo` | `hoy`, `semana`, `mes` (default), `custom` |
| `fecha_desde` | `YYYY-MM-DD` (con `periodo=custom`) |
| `fecha_hasta` | `YYYY-MM-DD` (con `periodo=custom`) |
| `proyecto_id` | ID del proyecto (si el líder tiene varios asignados) |
| `page` | Número de página para la tabla de últimos registros |

### Formulario de registro

- **Multi-fila:** el líder agrega N filas, una por cada combinación digitalizador + etapa.
- **Visibilidad dinámica:** los campos se muestran/ocultan con JavaScript según la etapa seleccionada.
- **Bloqueo de fecha futura:** el datepicker tiene `max = fecha_hoy` — no permite seleccionar fechas futuras.
- **Límites HTML:** `min="0"` y `max="999999"` en todos los campos numéricos; `maxlength` en campos de texto.

---

## API REST interna

**Ruta:** `POST /digitalizacion/api/v1/proyectos/<id>/registros`  
**Autenticación:** `auth=user` + CSRF token de Odoo  
**Content-Type:** `application/json`

### Estructura del payload

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "fecha": "2026-04-03",
    "filas": [
      {
        "miembro_id": 42,
        "etapa_id": 1,
        "no_expedientes": 15,
        "total_folios": 120,
        "total_escaneos": 0,
        "tipo_escaner_ids": [],
        "expedientes_editados": 0,
        "folios_editados": 0,
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

```json
{ "result": { "success": true } }

{ "result": { "success": false, "error": { "message": "Descripción del error" } } }
```

### Validaciones del controller (antes de llegar al ORM)

| Validación | Descripción |
|-----------|-------------|
| Formato de fecha | Debe ser `YYYY-MM-DD`, no futura |
| Tipo de `filas` | Debe ser un array, mínimo 1 elemento |
| Límite de filas | Máximo **50 filas** por request |
| `miembro_id` / `etapa_id` | Entero positivo obligatorio |
| Campos numéricos | Entero, entre 0 y 999 999 |
| `referencia_cajas` | String, máx. 200 chars, debe contener al menos 1 alfanumérico |
| `observacion` | String, máx. 2 000 chars |
| Acceso al proyecto | El líder debe tener asignación activa |

---

## Vistas de administración

Accesibles desde el menú principal **Digitalización** (solo rol Administrador).

| Menú | Vista | Descripción |
|------|-------|-------------|
| Proyectos | Lista + Kanban + Formulario | Gestión completa de proyectos |
| Asignaciones | Lista + Formulario | Control de líderes por proyecto |
| Miembros | Lista + Formulario | Gestión del equipo por proyecto |
| Registros | Lista + Formulario + Pivot + Gráfico | Análisis de producción diaria |
| Configuración → Etapas | Lista + Formulario | Catálogo de etapas del proceso |
| Configuración → Escáneres | Lista + Formulario | Catálogo de equipos |
| Dashboard | Vista especial | KPIs globales de producción |

---

## Validaciones implementadas

### Nivel Python (`@api.constrains`)

| Modelo | Constraint | Regla |
|--------|-----------|-------|
| `etapa` | `_check_name` | Nombre no vacío, no solo dígitos, no solo símbolos |
| `etapa` | `_check_sequence` | Secuencia ≥ 0 |
| `tipo_escaner` | `_check_name` | Nombre no vacío, no solo dígitos |
| `asignacion` | `_check_lider_tiene_grupo` | El usuario debe pertenecer al grupo Líder |
| `asignacion` | `_check_fecha_asignacion` | Fecha de asignación no futura |
| `proyecto` | `_check_fechas` | `fecha_fin ≥ fecha_inicio` |
| `proyecto` | `_check_meta_escaneos` | `0 ≤ meta_escaneos ≤ 100 000 000` |
| `proyecto` | `_check_name` | Nombre no vacío, no solo dígitos |
| `proyecto` | `_check_description_longitud` | Descripción ≤ 5 000 caracteres |
| `miembro_proyecto` | `_check_fechas` | `fecha_salida ≥ fecha_integracion` |
| `miembro_proyecto` | `_check_lider_unico` | Solo 1 líder activo por proyecto |
| `registro` | `_check_fecha_no_futura` | `fecha ≤ hoy` |
| `registro` | `_check_valores_positivos` | Todos los campos numéricos: `0 ≤ valor ≤ 999 999` |
| `registro` | `_check_campos_minimos_por_etapa` | Cada etapa exige al menos un campo de producción > 0 |
| `registro` | `_check_miembro_activo` | El digitalizador no debe tener fecha de salida |
| `registro` | `_check_miembro_pertenece_proyecto` | El digitalizador debe pertenecer al proyecto |
| `registro` | `_check_referencia_cajas` | No vacía, contiene al menos 1 carácter alfanumérico |
| `registro` | `_check_observacion_longitud` | Observación ≤ 2 000 caracteres |

### Nivel SQL (`_sql_constraints`)

| Modelo | Constraint |
|--------|-----------|
| `etapa` | `UNIQUE(name)` |
| `tipo_escaner` | `UNIQUE(name)` |
| `proyecto` | `UNIQUE(name)` |
| `asignacion` | `UNIQUE(lider_id, proyecto_id)` |
| `miembro_proyecto` | `UNIQUE(proyecto_id, partner_id)` |

### Nivel HTML (Portal)

- `<input type="number">` con `min="0"` y `max="999999"`
- `<input type="text">` con `maxlength` correspondiente
- `<input type="date">` con `max` = fecha actual (vía JavaScript)

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
| `test_proyecto_unitario.py` | `TestProyectoUnitario` | 14 | Caja blanca | PY-01 a PY-07: fechas, progreso, constraints |
| `test_miembro_unitario.py` | `TestMiembroUnitario` | 13 | Caja blanca | MP-01 a MP-07: liderazgo, salida, unicidad |

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
│       │   ├── proyecto.py
│       │   ├── registro.py
│       │   └── tipo_escaner.py
│       ├── security/
│       │   ├── digitalizacion_groups.xml
│       │   ├── digitalizacion_proyecto_security.xml
│       │   ├── digitalizacion_registro_security.xml
│       │   └── ir.model.access.csv
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── test_miembro_unitario.py
│       │   ├── test_proyecto_unitario.py
│       │   ├── test_registro_regresion.py
│       │   └── test_registro_unitario.py
│       └── views/
│           ├── admin/
│           │   ├── configuracion/
│           │   │   ├── etapa_views.xml
│           │   │   └── tipo_escaner_views.xml
│           │   ├── operaciones/
│           │   │   ├── miembro_views.xml
│           │   │   └── registro_views.xml
│           │   ├── proyectos/
│           │   │   ├── asignacion_views.xml
│           │   │   └── proyecto_views.xml
│           │   ├── dashboard_views.xml
│           │   └── digitalizacion_menus.xml
│           └── portal/
│               ├── portal_home_templates.xml
│               ├── portal_miembros_templates.xml
│               ├── portal_proyecto_templates.xml
│               ├── portal_registro_form_templates.xml
│               └── website_menu.xml
├── docker-compose.yaml
├── odoo.conf
└── README.md
```

---

## Entorno Docker

El proyecto incluye un entorno Docker con dos contenedores:

| Contenedor | Imagen | Puerto |
|-----------|--------|--------|
| `odoo.17.otecglobal` | Odoo 17 | `8001` (HTTP), `8002` (longpolling) |
| `postgres.db.otec` | PostgreSQL | `5432` |

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
- **Portal — fetch nativo:** El formulario de registro usa `fetch()` nativo con CSRF token de Odoo, sin `odoo.define` ni `web.rpc` (deprecados en portal Odoo 17).
- **lider_id en registros:** El campo `lider_id` se asigna automáticamente en `create()` al usuario en sesión y no puede modificarse mediante `write()`.

---

*Desarrollado como aporte de la Práctica Profesional · OTEC GLOBAL · 2026*