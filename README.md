# Módulo de Gestión de Digitalización

### `digitalizacion` — Módulo custom para Odoo 17 | OTEC GLOBAL

> Desarrollado como práctica profesional supervisada.
> Gestiona proyectos de digitalización de documentos físicos: equipos, producción diaria, etapas y métricas.

---

## Tabla de contenido

1. [Descripción general](#1-descripción-general)
2. [Roles del sistema](#2-roles-del-sistema)
3. [Arquitectura](#3-arquitectura)
4. [Modelos de datos](#4-modelos-de-datos)
5. [Estructura del módulo](#5-estructura-del-módulo)
6. [Vistas del Admin](#6-vistas-del-admin)
7. [Portal del Líder](#7-portal-del-líder)
8. [Seguridad y acceso](#8-seguridad-y-acceso)
9. [Flujo funcional](#9-flujo-funcional)
10. [Instalación](#10-instalación)
11. [Autora](#11-autora)

---

## 1. Descripción general

El módulo `digitalizacion` permite gestionar integralmente proyectos de digitalización de documentos físicos sobre **Odoo 17 Community**.

El modelo operativo es el siguiente: los digitalizadores trabajan en grupos, pero **solo el líder del equipo tiene acceso al sistema**. El líder accede al **portal web de Odoo** y registra la producción diaria del equipo completo al final de cada jornada. El administrador gestiona todo desde el backoffice y monitorea el avance mediante dashboards.

**Capacidades del sistema:**

- Crear y administrar proyectos con fechas, meta de escaneos y estado de progreso.
- Asignar líderes responsables por proyecto y gestionar el equipo de digitalizadores.
- Registrar producción diaria por miembro, etapa y caja procesada.
- Visualizar métricas de avance, tendencia diaria y comparativa por digitalizador.

---

## 2. Roles del sistema

El sistema define dos roles con accesos completamente separados.

### Administrador — `Gestión de Digitalización / Administrador`

- Accede al **backend de Odoo** (interfaz completa).
- Crea y administra proyectos, etapas y tipos de escáner.
- Asigna líderes de equipo y gestiona miembros.
- Visualiza todos los registros de trabajo y el dashboard global.

### Líder de equipo — `Gestión de Digitalización / Líder de equipo`

- Accede **únicamente al portal web** de Odoo.
- Solo ve los proyectos donde tiene una asignación activa.
- Registra la producción diaria del equipo (formulario multi-fila).
- Gestiona los miembros de su equipo (agregar, consultar).
- No tiene acceso al backend ni a proyectos de otros líderes.

### Miembros del equipo (digitalizadores)

- **No tienen usuario en Odoo.** Son contactos (`res.partner`) vinculados al proyecto.
- Su producción es ingresada por el Líder desde el portal.

### Tabla de permisos

| Acción | Admin | Líder |
|---|---|---|
| Crear / editar proyectos | ✅ | ❌ |
| Ver todos los proyectos | ✅ | ❌ |
| Ver sus proyectos asignados | ✅ | ✅ |
| Asignar líderes | ✅ | ❌ |
| Gestionar miembros del equipo | ✅ | ✅ solo su proyecto |
| Registrar producción diaria | ✅ | ✅ |
| Ver todos los registros | ✅ | ❌ |
| Ver registros de su proyecto | ✅ | ✅ |
| Configurar etapas y escáneres | ✅ | ❌ |
| Dashboard global | ✅ | ❌ |

---

## 3. Arquitectura

```
┌──────────────────────────────────────────────┐
│         ADMIN — Odoo Backend                 │
│     Vistas XML · Odoo Web Client             │
└───────────────────┬──────────────────────────┘
                    │
┌──────────────────────────────────────────────┐
│         LÍDER — Portal Web                   │
│     Templates QWeb · Website Odoo            │
└───────────────────┬──────────────────────────┘
                    │
┌──────────────────────────────────────────────┐
│         CONTROLLERS                          │
│     /digitalizacion/* · Python HTTP          │
│  Autenticación · Permisos · Lógica HTTP      │
└───────────────────┬──────────────────────────┘
                    │
┌──────────────────────────────────────────────┐
│         MODELS — ORM Odoo                    │
│  digitalizacion.* · Reglas de negocio        │
│  constrains · onchange · compute             │
└───────────────────┬──────────────────────────┘
                    │
┌──────────────────────────────────────────────┐
│         PostgreSQL                           │
└──────────────────────────────────────────────┘
```

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Vistas Admin | XML — Odoo Views | Backoffice del administrador |
| Portal Líder | QWeb + HTML/CSS/JS | Interfaz web del líder |
| Controllers | Python `http.Controller` | Rutas HTTP, validación, puente portal ↔ modelos |
| Models | Python `models.Model` | Lógica de negocio, validaciones, cálculos |
| Seguridad | CSV + XML `ir.rule` | RBAC, grupos y reglas de registro |

---

## 4. Modelos de datos

| Modelo | Tabla SQL | Descripción |
|---|---|---|
| `digitalizacion.etapa` | `digitalizacion_etapa` | Catálogo de etapas del proceso (Limpieza, Digitalizado, Editado, Indexado, Ordenado) |
| `digitalizacion.tipo_escaner` | `digitalizacion_tipo_escaner` | Catálogo global de equipos escáneres |
| `digitalizacion.proyecto` | `digitalizacion_proyecto` | Registro central de proyectos |
| `digitalizacion.asignacion` | `digitalizacion_asignacion` | Relación Líder ↔ Proyecto. `UNIQUE(lider_id, proyecto_id)` |
| `digitalizacion.miembro_proyecto` | `digitalizacion_miembro_proyecto` | Digitalizadores vinculados a un proyecto. `UNIQUE(proyecto_id, partner_id)` |
| `digitalizacion.registro` | `digitalizacion_registro` | Tabla principal: producción diaria por miembro y etapa |

### Relaciones principales

| Origen | Campo | Destino | Tipo |
|---|---|---|---|
| `asignacion` | `lider_id` | `res.users` | Many2one |
| `asignacion` | `proyecto_id` | `digitalizacion.proyecto` | Many2one |
| `miembro_proyecto` | `partner_id` | `res.partner` | Many2one |
| `miembro_proyecto` | `proyecto_id` | `digitalizacion.proyecto` | Many2one |
| `registro` | `lider_id` | `res.users` | Many2one (auditoría) |
| `registro` | `miembro_id` | `digitalizacion.miembro_proyecto` | Many2one |
| `registro` | `proyecto_id` | `digitalizacion.proyecto` | Many2one |
| `registro` | `etapa_id` | `digitalizacion.etapa` | Many2one |
| `registro` | `tipo_escaner_ids` | `digitalizacion.tipo_escaner` | Many2many |

### Granularidad del registro

> 1 registro = 1 miembro + 1 etapa + cantidades acumuladas del día

El Líder agrega N registros al final de la jornada, uno por cada combinación miembro+etapa trabajada. Un mismo miembro puede tener múltiples registros en el mismo día si trabajó en varias etapas.

Los campos de producción son opcionales y se muestran/ocultan según la etapa:

| Etapa | Campos activos |
|---|---|
| Limpieza / Ordenado | `no_caja`, `cantidad_cajas`, `no_expedientes`, `total_folios` |
| Digitalizado | `total_folios`, `total_escaneos`, `tipo_escaner_ids` |
| Editado | `expedientes_editados`, `folios_editados` |
| Indexado | `expedientes_indexados`, `folios_indexados` |

---

## 5. Estructura del módulo

```
digitalizacion/
├── __init__.py
├── __manifest__.py
│
├── models/
│   ├── __init__.py
│   ├── etapa.py
│   ├── tipo_escaner.py
│   ├── proyecto.py
│   ├── asignacion.py
│   ├── miembro_proyecto.py
│   └── registro.py
│
├── controllers/
│   ├── __init__.py
│   └── portal.py
│
├── views/
│   ├── admin/                          ← Todo el backoffice del Admin
│   │   ├── proyectos/
│   │   │   ├── proyecto_views.xml
│   │   │   └── asignacion_views.xml
│   │   ├── operaciones/
│   │   │   ├── miembro_views.xml
│   │   │   └── registro_views.xml
│   │   ├── configuracion/
│   │   │   ├── etapa_views.xml
│   │   │   └── tipo_escaner_views.xml
│   │   ├── dashboard/
│   │   │   └── dashboard_admin.xml
│   │   └── menus.xml                   ← Árbol de menús consolidado
│   │
│   └── portal/                         ← Portal web del Líder (QWeb)
│       ├── portal_home.xml
│       ├── portal_proyecto.xml
│       ├── portal_registro_form.xml
│       └── portal_miembros.xml
│
├── security/
│   ├── security.xml                    ← Categoría, grupos y reglas ir.rule
│   └── ir.model.access.csv             ← Permisos CRUD por modelo y grupo
│
└── data/
    └── etapas_default.xml              ← Etapas iniciales del proceso
```

### Orden de carga en `__manifest__.py`

El orden es estricto en Odoo — un `menuitem` no puede referenciar una acción que aún no existe en la BD:

```
1. security/          → grupos y ACLs primero
2. data/              → datos maestros
3. views/admin/*_views.xml  → vistas y acciones
4. views/admin/menus.xml    → menús (siempre al final)
5. views/portal/      → templates QWeb
```

---

## 6. Vistas del Admin

### Menú de navegación

```
Digitalización
├── Dashboard
├── Proyectos
│   ├── Proyectos
│   └── Asignar Líderes
├── Operaciones
│   ├── Miembros del Equipo
│   └── Registros de Trabajo
└── Configuración
    ├── Etapas
    └── Tipos de Escáner
```

### Archivos de vistas

| Archivo | Vistas incluidas |
|---|---|
| `proyectos/proyecto_views.xml` | Lista, Kanban, Formulario con pestañas de Líderes y Miembros, búsqueda |
| `proyectos/asignacion_views.xml` | Lista, Formulario, búsqueda |
| `operaciones/miembro_views.xml` | Lista, Formulario con stat buttons, búsqueda |
| `operaciones/registro_views.xml` | Lista con totales, Formulario con campos dinámicos por etapa, Pivot, Graph, búsqueda |
| `configuracion/etapa_views.xml` | Lista editable inline, Formulario |
| `configuracion/tipo_escaner_views.xml` | Lista editable inline, Formulario |
| `dashboard/dashboard_admin.xml` | Graph por digitalizador (barras), Graph tendencia diaria (línea), Pivot, filtros de período |

---

## 7. Portal del Líder

### Rutas HTTP

| Método | Ruta | Template | Descripción |
|---|---|---|---|
| `GET` | `/digitalizacion` | `wf02_dashboard` | Dashboard del líder con KPIs y registros recientes |
| `GET` | `/digitalizacion/registro/<proyecto_id>` | `wf03_formulario` | Formulario multi-fila de registro de producción |
| `GET` | `/digitalizacion/proyecto/<proyecto_id>` | `wf04_proyecto_detalle` | Detalle del proyecto |
| `GET` | `/digitalizacion/proyecto/<proyecto_id>/miembros` | `wf05_miembros_equipo` | Gestión del equipo |
| `POST` | `/digitalizacion/api/guardar_registros` | — | Guardado masivo de registros (JSON-RPC) |
| `POST` | `/digitalizacion/api/buscar_partner` | — | Búsqueda de contactos por nombre |
| `POST` | `/digitalizacion/api/agregar_miembro` | — | Vincula un contacto al proyecto |

### Templates QWeb

| Archivo | Template | Descripción |
|---|---|---|
| `portal_home.xml` | `wf02_dashboard` | KPIs del período, producción por etapa, registros recientes |
| `portal_proyecto.xml` | `wf04_proyecto_detalle` | Datos del proyecto, progreso, accesos rápidos |
| `portal_registro_form.xml` | `wf03_formulario` | Tabla dinámica con filas por miembro+etapa, campos visibles según etapa seleccionada |
| `portal_miembros.xml` | `wf05_miembros_equipo` | Lista del equipo, modal para agregar miembros con búsqueda en vivo |

### Notas de implementación del portal

- El JS del formulario usa `fetch` nativo (no `odoo.define` / `web.rpc`, deprecados en Odoo 17 para el portal).
- La visibilidad de columnas por etapa se controla via JavaScript con el mapa `reglasEtapa`.
- El modal de miembros implementa búsqueda con debounce a `/api/buscar_partner` y crea contactos nuevos si no existen.

---

## 8. Seguridad y acceso

### Grupos

Definidos bajo la categoría **Gestión de Digitalización** (visible en Ajustes → Usuarios):

| XML ID | Nombre visible | Acceso |
|---|---|---|
| `group_digitalizacion_admin` | Administrador | Backend completo |
| `group_digitalizacion_lider` | Líder de equipo | Solo portal web |

### Reglas de registro (`ir.rule`)

| Regla | Modelo | Efecto |
|---|---|---|
| `rule_lider_solo_sus_proyectos` | `digitalizacion.proyecto` | El líder solo ve proyectos donde tiene asignación activa |
| `rule_lider_solo_sus_registros` | `digitalizacion.registro` | El líder solo ve registros de sus proyectos |

### Permisos CRUD por modelo

| Modelo | Admin | Líder |
|---|---|---|
| `digitalizacion.etapa` | CRUD | R |
| `digitalizacion.tipo_escaner` | CRUD | R |
| `digitalizacion.proyecto` | CRUD | R |
| `digitalizacion.asignacion` | CRUD | R |
| `digitalizacion.miembro_proyecto` | CRUD | RWC |
| `digitalizacion.registro` | CRUD | RWC |
| `res.partner` | — | R |

### Cómo crear un usuario Líder

> ⚠️ Los usuarios Portal **no se crean desde Ajustes → Usuarios** — quedarían como Internos.

1. Ir a **Contactos** → crear contacto con nombre y correo.
2. En la ficha: **Acción ⚙️ → Otorgar acceso al portal** → tildar "En el Portal" → Aplicar.
3. Ir a **Ajustes → Usuarios → Grupos** → buscar **Gestión de Digitalización / Líder de equipo** → agregar el usuario.

---

## 9. Flujo funcional

```
ADMIN
 ├─ 1. Crea el proyecto (nombre, fechas, meta de escaneos)
 ├─ 2. Asigna un Líder → el sistema lo agrega automáticamente como miembro
 └─ 3. Agrega digitalizadores al equipo desde la pestaña Miembros

LÍDER (portal web)
 ├─ 4. Inicia sesión → ve sus proyectos activos en el dashboard
 ├─ 5. Entra al formulario de registro del proyecto
 ├─ 6. Agrega una fila por cada miembro+etapa trabajada
 │       ├─ Selecciona digitalizador y etapa
 │       ├─ Los campos se habilitan según la etapa elegida
 │       └─ Ingresa cantidades (escaneos, folios, expedientes)
 └─ 7. Envía → los registros se crean en Odoo vía JSON-RPC

SISTEMA (automático)
 ├─ 8. Calcula progreso del proyecto: (escaneos / meta) × 100
 └─ 9. Actualiza produccion_principal y unidad_produccion por registro

ADMIN (dashboard)
 └─ 10. Visualiza:
         ├─ Progreso por proyecto (barras de avance)
         ├─ Producción por digitalizador (gráfico de barras)
         ├─ Tendencia diaria de escaneos (gráfico de línea)
         └─ Pivot cruzado por proyecto / miembro / etapa
```

---

## 10. Instalación

### Requisitos

- Odoo 17 Community
- Python 3.10+
- PostgreSQL 14+
- Docker y Docker Compose

### Primera instalación (BD limpia)

```bash
# 1. Clonar el repositorio en la carpeta de addons
git clone <repo-url> ./addons/digitalizacion

# 2. Levantar el entorno
docker compose up -d

# 3. Abrir http://localhost:<WEB_PORT>/web/database/manager
#    Crear una BD nueva (demo data: desactivado)

# 4. Instalar desde Aplicaciones → buscar "Digitalización" → Instalar
#    (activar modo desarrollador primero si no aparece)
```

### Actualizar tras cambios en el código

```bash
# Opción A — actualización sin borrar datos (cambios en vistas o lógica)
docker compose down
docker compose run --rm web odoo \
    -c /etc/odoo/odoo.conf \
    -u digitalizacion_dev \
    --stop-after-init
docker compose up -d

# Opción B — BD limpia (cambios en modelos: campos renombrados, tipos cambiados)
docker compose down
docker volume rm $(docker volume ls -q | grep odoo)
docker compose up -d
```

> **Cuándo usar la Opción B:** siempre que se renombre un campo, cambie su tipo (ej. Many2one → Many2many) o se elimine un campo que ya tiene datos. Odoo no migra estos cambios automáticamente sin un script de migración.

### Configuración inicial post-instalación

1. **Digitalización → Configuración → Etapas** — verificar las etapas cargadas por defecto.
2. **Digitalización → Configuración → Tipos de Escáner** — agregar los equipos disponibles.
3. Crear los contactos de los digitalizadores en **Contactos**.
4. Crear usuarios Líderes siguiendo el proceso de usuario Portal (ver [Sección 8](#8-seguridad-y-acceso)).
5. Crear el primer proyecto en **Digitalización → Proyectos → Proyectos**.
6. Asignar el Líder al proyecto en **Digitalización → Proyectos → Asignar Líderes**.

---

## 11. Autora

| Campo | Detalle |
|---|---|
| **Desarrolladora** | Jimena Castro |
| **Empresa** | OTEC GLOBAL — Oficinas Tecnológicas |
| **Contexto** | Práctica Profesional Supervisada (PPS) |
| **Universidad** | Universidad Católica de Honduras (UNICAH) |
| **Carrera** | Ingeniería en Ciencias de la Computación |
| **Período** | Febrero – Abril 2026 |

---

*Última actualización: Día 32 — Sábado 14 de Marzo, 2026*

docker exec odoo.17.otecglobal odoo -u digitalizacion -d postgres --stop-after-init