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
│   │   │   ├── proyecto_views.xml        # Vistas de proyecto
│   │   │   ├── proyecto_search.xml       # Búsqueda y filtros
│   │   │   ├── proyecto_actions.xml      # Acciones de ventana
│   │   │   └── registro_views.xml        # Vistas de registros
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
│   │   └── icon.png
│   └── src/
│       └── portal/
│           ├── js/
│           │   └── portal_registro_form.js   # Componente OWL reactivo
│           └── css/
│               └── portal_digitalizacion.css # Estilos CSS con variables
│
└── tests/
    ├── test_digitalizacion_v2.py
    └── test_digitalizacion_portal.py
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

---

### T-04 · `digitalizacion.asignacion` — Asignación Líder ↔ Proyecto

Tabla puente entre un usuario portal (Líder) y un proyecto. **Se crea automáticamente** cuando se marca `es_lider=True` en el miembro.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `lider_id` | Many2one (res.users) | Usuario portal con rol Líder |
| `proyecto_id` | Many2one | Proyecto asignado |
| `fecha_asignacion` | Date | Fecha de asignación (no puede ser futura) |
| `active` | Boolean | Soft delete — controla acceso al portal |

**Constraint SQL:** `UNIQUE(lider_id, proyecto_id)`.

---

### T-05 · `digitalizacion.miembro_proyecto` — Equipo por proyecto (MEJORADO)

Integrantes del equipo de digitalización. Un mismo contacto puede pertenecer a múltiples proyectos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `proyecto_id` | Many2one | Proyecto al que pertenece |
| `partner_id` | Many2one (res.partner) | Contacto del integrante |
| `fecha_integracion` | Date | Fecha de incorporación |
| `fecha_salida` | Date | Si está informada, excluye al miembro del formulario de registro |
| `es_lider` | Boolean | Marca como líder — sincroniza con T-04 y grupo automáticamente |
| `is_active` | Boolean (compute) | Calculado como: `fecha_salida == False` |

**Campos computados:**
- `total_registros`: Registros de trabajo emitidos

**Constraint SQL:** `UNIQUE(proyecto_id, partner_id)`.  
**Regla de negocio:** Solo puede haber **un líder activo** por proyecto.

#### Gestión de liderazgo

Cuando `es_lider=True`:
1. **Validar usuario portal:** El partner debe tener un usuario portal (`share=True`)
2. **Asignar grupo líder:** Se añade automáticamente el grupo `group_digitalizacion_lider` al usuario
3. **Desmarcar otros líderes:** Se desmarca `es_lider` en otros miembros del mismo proyecto
4. **Crear/reactivar asignación:** Se crea o reactiva el registro en T-04

Cuando `es_lider=False`:
1. **Remover grupo (inteligente):** Solo se quita el grupo si el usuario **no es líder en otros proyectos**
2. **Desactivar asignación:** Se desactiva el registro en T-04

Cuando se informa `fecha_salida`:
1. **Desactivar miembro:** Se marca como `active=False`
2. **Limpiar liderazgo:** Si es líder, se desactiva automáticamente
3. **Permitir reactivación:** Un miembro archivado con salida puede ser reactivado (se limpia `fecha_salida`)

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

---

## Seguridad y permisos

### Grupos

| Grupo | Hereda de | Acceso |
|-------|-----------|--------|
| **Administrador** | `base.group_user` | Backoffice completo: proyectos, registros, catálogos, dashboard |
| **Líder de equipo** | `base.group_portal` | Solo portal web: registrar producción diaria |

**Asignación automática:** El grupo Líder se asigna automáticamente cuando se marca `es_lider=True` en un miembro. Se remueve cuando ya no es líder en ningún proyecto.

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
| **Digitalizador (miembro_id)** | Requerido; solo miembros activos (sin `fecha_salida`) |
| **Etapa (etapa_id)** | Requerido |
| **Campos numéricos** | 0 ≤ valor ≤ 999 999; entero (no decimales) |
| **Referencia de cajas** | Máx. 200 chars; debe contener al menos 1 alfanumérico |
| **Observación** | Máx. 500 caracteres |
| **Producción mínima** | Al menos 1 campo de producción > 0 según etapa |
| **Escáner (si Digitalizado)** | Obligatorio si `etapa_id = Digitalizado` |

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
    "fecha": "2026-04-17",
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
| Miembro activo | El miembro no debe tener `fecha_salida` |

---

## Vistas de administración

Accesibles desde el menú principal **Digitalización** (solo rol Administrador).

### Estructura del menú

| Menú | Descripción |
|------|-------------|
| **Proyectos** | Gestión unificada de líderes, personal, dashboard y reportes |
| **Dashboard** | Análisis global de producción con gráficos (línea, barras, pivot) |
| **Configuración** | Catálogos de etapas y escáneres |

### Vistas de Proyectos

El módulo implementa múltiples vistas separadas para mejor organización:

#### 1. **Vista de búsqueda (proyecto_search.xml)**
- Filtros rápidos: Activos, Archivados, Por estado
- Agrupación por: Estado, Fecha de inicio

#### 2. **Vista Kanban (proyecto_views.xml)**
- Tarjetas agrupadas por estado (`en_curso`, `pausado`, `finalizado`)
- KPIs resumidos (miembros, escaneos, registros, duración)
- Iconos representativos por estado
- Icono de archivo para proyectos inactivos

#### 3. **Vista de lista (proyecto_views.xml)**
- Ordenada por fecha de inicio descendente
- Colores decorativos por estado
- Columnas: Proyecto, Inicio, Estado, Miembros, Escaneos

#### 4. **Vista de formulario (proyecto_views.xml)**

**Pestañas incluidas:**

1. **Dashboard:**
   - KPIs: Escaneos totales, Registros, Etapa dominante, Duración estimada
   - Botón "ABRIR ANÁLISIS GRÁFICO" para ver líneas de tendencia

2. **Miembros de Equipo:**
   - Tabla inline editable con digitalizadores
   - Checkbox para marcar líder del proyecto
   - Cómputo automático de registros por miembro
   - Sincronización automática de grupos y asignaciones

3. **Bitácora:**
   - Vistas de registros (tree, form, pivot, graph)
   - Análisis cruzado de producción por miembro, etapa y fecha

#### 5. **Vistas de Registros**

- **Tree (lista):** Ordenada por fecha descendente
- **Form:** Con visibilidad dinámica de campos por etapa
- **Pivot:** Análisis cruzado (Proyecto × Miembro × Etapa)
- **Graph:** Tendencia diaria de producción (línea)

#### 6. **Dashboard global**

Accesible desde menú. Ofrece:
- **Graph (Línea):** Tendencia diaria de escaneos
- **Graph (Barras):** Producción por digitalizador
- **Pivot:** Análisis cruzado de todos los proyectos
- Filtros por proyecto, etapa, fecha

### Acciones de ventana (proyecto_actions.xml)

1. **Gestión de Proyectos (principal):**
   - Vista por defecto: Kanban agrupado por estado
   - Contexto: filtro automático de proyectos activos

2. **Proyectos Archivados:**
   - Vista separada para gestionar proyectos inactivos
   - Permite ver y reactivar proyectos

---

## Validaciones implementadas

### Nivel Python (`@api.constrains`)

| Modelo | Constraint | Regla |
|--------|-----------|-------|
| `etapa` | `_check_name` | Nombre no vacío, no solo dígitos |
| `etapa` | `_check_sequence` | Secuencia ≥ 0 |
| `tipo_escaner` | `_check_name` | Nombre no vacío, no solo dígitos |
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
- `<input type="text">` con `maxlength` correspondiente
- `<input type="date">` con `max` = fecha actual (vía JavaScript)
- Validación reactiva en tiempo real con OWL
- Mensajes de error inline contextualizados por campo

---

## Reportes PDF

### Reporte de Proyecto (QWeb)

**Acción:** Disponible desde el botón en el formulario del Proyecto

**Contenido:**
- Cabecera con nombre del proyecto y estado (con badges de color)
- Matriz de 4 KPIs: Integrantes, Escaneos, Producciones, Días Estimados
- Configuración del proyecto: Fechas, Líderes de Operación
- Desglose de producción acumulada por etapa (tabla)
- Equipo de trabajo asignado con roles (Líder ★ y Digitalizador)

---

## Pruebas automatizadas
 
### Ejecutar todo el modulo
 
```bash
docker exec odoo.17.otecglobal odoo \
  -c /etc/odoo/odoo.conf \
  -d digitalizacion_dev \
  --test-enable \
  --stop-after-init \
  --test-tags=digitalizacion
```
 
### Ejecutar pruebas del portal (con acceso HTTP)
 
Para ejecutar las pruebas del portal con acceso HTTP en un puerto alternativo:
 
```bash
docker exec -it odoo.17.otecglobal odoo \
  -u digitalizacion \
  --test-enable \
  --stop-after-init \
  -d digitalizacion_dev \
  --test-tags=digitalizacion \
  --http-port=8070
```
 
Esta opción permite que las pruebas que requieren acceso al servidor HTTP (como las del portal) se ejecuten correctamente en el puerto `8070`, evitando conflictos con el servidor principal en `8001`.

### Ejecución de Pruebas

| Archivo | Clase | Cobertura |
|---------|-------|-----------|
| `test_digitalizacion_v2.py` | Pruebas V2 del módulo | Validaciones, sincronización, liderazgo |
| `test_digitalizacion_portal.py` | Pruebas del portal | Rutas, API, validaciones |

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
│       │   ├── test_digitalizacion_v2.py
│       │   └── test_digitalizacion_portal.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── constantes.py
│       │   └── utils.py
│       └── views/
│           ├── admin/
│           │   ├── configuracion/
│           │   │   ├── etapa_views.xml
│           │   │   └── tipo_escaner_views.xml
│           │   ├── proyectos/
│           │   │   ├── proyecto_search.xml
│           │   │   ├── proyecto_views.xml
│           │   │   ├── proyecto_actions.xml
│           │   │   └── registro_views.xml
│           │   ├── dashboard_views.xml
│           │   └── digitalizacion_menus.xml
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

# Reiniciar servidor de odoo
docker restart odoo.17.otecglobal
```

---

## Cambios recientes (v17.0.2.0.0)

### Reorganización de vistas administrativas

1. **Vistas separadas por responsabilidad:**
   - `proyecto_search.xml`: Búsqueda y filtros
   - `proyecto_views.xml`: Kanban, list, form
   - `proyecto_actions.xml`: Acciones de ventana
   - `registro_views.xml`: Vistas de registros

2. **Mejora en acciones de ventana:**
   - Acción principal con contexto predeterminado
   - Acción separada para proyectos archivados
   - Mejor control de qué datos se ven por defecto

### Mejoras en gestión de liderazgo (miembro_proyecto.py)

1. **Asignación automática de grupos:**
   - Al marcar `es_lider=True`, se asigna automáticamente el grupo Líder
   - Sincronización inteligente: solo se quita el grupo si no es líder en otros proyectos

2. **Métodos específicos:**
   - `_activar_liderazgo()`: Valida usuario, asigna grupo, crea/reactiva asignación
   - `_desactivar_liderazgo()`: Verifica otros proyectos, quita grupo si es necesario
   - `_desactivar_asignacion_sin_remover_grupo()`: Desactiva asignación sin tocar grupo

3. **Reactivación de miembros:**
   - Si un miembro archivado (con `fecha_salida`) se intenta crear nuevamente, se reactiva automáticamente
   - El patrón `create()` implementa reactivar-si-existe, crear-si-no-existe

### Mejoras en el campo `is_active`

- Campo `is_active` computado (basado en `fecha_salida`)
- Facilita consultas de miembros activos sin duplicar lógica
- Almacenado para mejor rendimiento en búsquedas

---

## Notas de desarrollo

- **Odoo 17 — sintaxis de vistas:** Se usan expresiones Python directas en `invisible=""`.
- **QWeb — operadores en XML:** Los operadores `>`, `>=`, `<`, `<=` deben escaparse (`&gt;`, `&lt;`).
- **Framework OWL:** Componente reactivo para formulario multi-fila con validación en tiempo real.
- **Principio DRY:** Constantes centralizadas, validadores puros, mixins reutilizables.
- **Seguridad en capas:** ACLs + ir.rules para protección en dos niveles.
- **Sincronización automática:** Los cambios en miembros se propagan a asignaciones y grupos automáticamente.

---

*Desarrollado como aporte de la Práctica Profesional · OTEC GLOBAL · Febrero-Abril 2026*