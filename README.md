# 📄 Módulo de Gestión de Digitalización
### `digitalizacion` — Módulo custom para Odoo 17 | OTEC GLOBAL

> Módulo desarrollado como aporte de práctica profesional supervisada.  
> Gestiona proyectos de digitalización de documentos físicos: equipos, producción diaria, etapas y métricas.

---

## Tabla de contenido

1. [Descripción general](#1-descripción-general)
2. [Objetivos del sistema](#2-objetivos-del-sistema)
3. [Arquitectura del sistema](#3-arquitectura-del-sistema)
4. [Roles del sistema](#4-roles-del-sistema)
8. [API del portal — Controllers](#8-api-del-portal--controllers)
9. [Organización de vistas por rol](#9-organización-de-vistas-por-rol)
10. [Flujo funcional del sistema](#10-flujo-funcional-del-sistema)
11. [Estructura del módulo](#11-estructura-del-módulo)
12. [Seguridad y control de acceso](#12-seguridad-y-control-de-acceso)
15. [Instalación del módulo](#15-instalación-del-módulo)
16. [Consideraciones técnicas](#16-consideraciones-técnicas)
17. [Autor](#17-autor)

---

## 1. Descripción general

El módulo `digitalizacion` es un módulo custom desarrollado sobre **Odoo 17** para **OTEC GLOBAL**. Su propósito es gestionar de forma integral los proyectos de digitalización de documentos físicos que la empresa ejecuta para sus clientes.

El sistema permite:

- Crear y administrar **proyectos de digitalización** con fechas, metas y estado de progreso.
- Asignar **líderes de equipo** responsables de cada proyecto.
- Gestionar los **miembros del equipo** que participan en cada proyecto.
- Registrar la **producción diaria** de cada digitalizador por etapa del proceso.
- Consultar **registros de trabajo** históricos y en tiempo real.
- Visualizar **métricas y dashboards** de avance por proyecto y por digitalizador.

El modelo operativo es el siguiente: los digitalizadores trabajan en grupos pero **solo el líder del equipo tiene acceso al sistema**. El líder accede a través del **portal web de Odoo** y es responsable de registrar la producción diaria del equipo completo, incluyendo la suya propia.

---

## 2. Objetivos del sistema

| # | Objetivo |
|---|---|
| 1 | Centralizar el registro de producción de todos los proyectos de digitalización en una única plataforma |
| 2 | Proveer al administrador visibilidad en tiempo real del avance de cada proyecto |
| 3 | Permitir al líder registrar la producción diaria del equipo desde el portal web sin necesidad de acceso al backend |
| 4 | Garantizar la trazabilidad por digitalizador, etapa y fecha |
| 5 | Generar métricas automáticas de progreso (% de avance, escaneos por día, comparativa por digitalizador) |
| 6 | Implementar control de acceso por roles (RBAC) que separe las responsabilidades de Admin y Líder |

---

## 3. Arquitectura del sistema

El módulo sigue la arquitectura estándar de Odoo con una capa adicional de portal web.

```
┌─────────────────────────────────────────────────────┐
│              USUARIO ADMIN (Backend)                │
│         Vistas XML — Odoo Web Client                │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│              USUARIO LÍDER (Portal)                 │
│         Templates QWeb — Portal Website             │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                 CONTROLLERS                         │
│          HTTP Routes — /digitalizacion/*            │
│   Validación de sesión · Permisos · Lógica HTTP     │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                   MODELS (ORM)                      │
│     digitalizacion.* — Reglas de negocio            │
│     constrains · onchange · compute                 │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│              BASE DE DATOS                          │
│            PostgreSQL — Odoo ORM                    │
└─────────────────────────────────────────────────────┘
```

### Capas del sistema

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Portal | QWeb Templates + CSS | Interfaz del Líder (solo lectura/escritura de su proyecto) |
| Controllers | Python — `http.Controller` | Rutas HTTP, validación de sesión y permisos, puente portal ↔ modelos |
| Models | Python — `models.Model` | Lógica de negocio, validaciones, cálculos automáticos |
| Vistas Admin | XML — Odoo Views | Backoffice para el administrador |
| Seguridad | CSV + XML — `ir.rule` | RBAC, grupos de acceso y reglas de registro |
| Base de datos | PostgreSQL | Persistencia de datos vía ORM de Odoo |

---

## 4. Roles del sistema

El sistema define **dos roles principales** con accesos completamente diferenciados.

### Administrador (`Digitalización / Admin`)

- Accede al **backend de Odoo** (interfaz completa).
- Puede crear, editar y eliminar proyectos, etapas, tipos de escáner.
- Asigna líderes y gestiona miembros del equipo.
- Visualiza todos los registros de trabajo de todos los proyectos.
- Accede al dashboard con métricas globales.

### Líder de proyecto (`Digitalización / Líder`)

- Accede **únicamente al website** de Odoo.
- Solo ve los proyectos donde tiene una asignación activa.
- Registra la producción diaria del equipo (propia y de sus digitalizadores).
- Gestiona los miembros del equipo de sus proyectos.
- No tiene acceso al backend ni a proyectos de otros líderes.

### Miembros del equipo

- **No tienen usuario en Odoo**.
- Son registrados como contactos (`res.partner`) dentro del sistema.
- Su producción es ingresada por el Líder.

### Tabla de permisos

| Acción | Admin | Líder | Miembro |
|---|---|---|---|
| Crear proyecto | ✅ | ❌ | ❌ |
| Ver todos los proyectos | ✅ | ❌ | ❌ |
| Ver proyectos propios | ✅ | ✅ | ❌ |
| Asignar líder | ✅ | ❌ | ❌ |
| Gestionar miembros del equipo | ✅ | ✅ (solo su proyecto) | ❌ |
| Registrar producción diaria | ✅ | ✅ | ❌ |
| Ver todos los registros | ✅ | ❌ | ❌ |
| Ver registros de su proyecto | ✅ | ✅ | ❌ |
| Configurar etapas | ✅ | ❌ | ❌ |
| Configurar tipos de escáner | ✅ | ❌ | ❌ |
| Ver dashboard global | ✅ | ❌ | ❌ |

---

### Relaciones clave

| Relación | Tipo | Descripción |
|---|---|---|
| Proyecto → Asignaciones | One2many | Un proyecto puede tener uno o más líderes asignados |
| Proyecto → Miembros | One2many | Un proyecto tiene varios digitalizadores |
| Proyecto → Registros | One2many | Todos los registros de producción del proyecto |
| Asignación → `res.users` | Many2one | El líder debe ser un usuario portal de Odoo |
| Miembro → `res.partner` | Many2one | El digitalizador es un contacto (sin usuario) |
| Registro → Miembro | Many2one | A qué digitalizador corresponde la producción |
| Registro → Etapa | Many2one | En qué etapa del proceso trabajó |

---

## 8. API del portal — Controllers

Los controllers implementan las rutas HTTP que consume el portal del líder. Actúan como capa intermedia entre los templates QWeb y los modelos de Odoo.

### Responsabilidades del controller

- Verificar que el usuario tiene sesión activa (`request.env.user`).
- Validar que el líder tiene asignación activa en el proyecto solicitado.
- Preparar los datos necesarios para los templates QWeb.
- Procesar los formularios POST del portal (registro de producción, gestión de miembros).
- Retornar respuestas HTTP o redirecciones.

### Rutas HTTP principales

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/digitalizacion` | Dashboard del portal — lista de proyectos del líder |
| `GET` | `/digitalizacion/proyecto/<int:proyecto_id>` | Detalle del proyecto y sus registros |
| `GET` | `/digitalizacion/proyecto/<int:proyecto_id>/registros` | Listado de registros de trabajo |
| `POST` | `/digitalizacion/proyecto/<int:proyecto_id>/registro/nuevo` | Crear nuevo registro de producción |
| `GET` | `/digitalizacion/proyecto/<int:proyecto_id>/miembros` | Gestión de miembros del equipo |
| `POST` | `/digitalizacion/proyecto/<int:proyecto_id>/miembro/agregar` | Agregar miembro al equipo |

---

## 9. Organización de vistas por rol

Las vistas están organizadas por carpeta según el rol que las consume.

```
views/
├── admin/
│   ├── proyecto_views.xml          # Lista y form de proyectos
│   ├── asignacion_views.xml        # Asignación de líderes
│   └── menu_views.xml              # Menú principal Admin
│
├── operaciones/
│   ├── miembro_views.xml           # Gestión de miembros del equipo
│   ├── registro_views.xml          # Registros de trabajo (lista + form)
│   └── menu_operaciones.xml        # Submenú Operaciones
│
├── configuracion/
│   ├── etapa_views.xml             # CRUD de etapas
│   ├── tipo_escaner_views.xml      # CRUD de tipos de escáner
│   └── menu_configuracion.xml      # Submenú Configuración
│
├── portal/
│   ├── portal_home.xml             # Dashboard del líder
│   ├── portal_proyecto.xml         # Detalle del proyecto
│   ├── portal_registro_form.xml    # Formulario de registro de producción
│   └── portal_miembros.xml        # Gestión de miembros desde portal
│
└── dashboard/
    ├── dashboard_views.xml         # Vista principal del dashboard
    └── dashboard_kpi.xml           # KPIs y gráficas
```

### Menú de navegación Admin

```
Digitalización
├── Operaciones
│   ├── Proyectos
│   ├── Asignar Líderes
│   ├── Miembros del Equipo
│   └── Registros de Trabajo
└── Configuración
    ├── Etapas
    └── Tipos de Escáner
```

---

## 10. Flujo funcional del sistema

### Flujo completo: Admin → Líder → Registro → Dashboard

```
[ADMIN]
   │
   ├── 1. Crea el proyecto (nombre, fechas, meta de escaneos)
   │
   ├── 2. Asigna un Líder al proyecto
   │        └── El sistema crea automáticamente al líder como miembro del proyecto
   │
   ├── 3. Agrega miembros del equipo (digitalizadores)
   │
   └── 4. El proyecto queda activo y visible en el portal del Líder
   
[LÍDER — Portal Web]
   │
   ├── 5. Inicia sesión en el portal de Odoo
   │
   ├── 6. Ve sus proyectos activos asignados
   │
   ├── 7. Selecciona un proyecto y accede al formulario de registro
   │
   ├── 8. Registra la producción diaria:
   │        ├── Selecciona miembro del equipo
   │        ├── Selecciona etapa del proceso
   │        ├── Ingresa cantidad de escaneos
   │        └── Guarda el registro
   │
   └── 9. Puede ver el progreso acumulado del proyecto

[SISTEMA — Automático]
   │
   ├── 10. Calcula el progreso (%) del proyecto en tiempo real
   │         └── progreso = (suma escaneos registrados / meta_escaneos) × 100
   │
   └── 11. Actualiza el dashboard del Admin con las nuevas métricas

[ADMIN — Dashboard]
   │
   └── 12. Visualiza KPIs:
             ├── Total proyectos activos
             ├── Total registros del mes
             ├── Progreso por proyecto (gráfica de barras)
             ├── Producción por digitalizador
             └── Promedio de escaneos por día
```

---

## 11. Estructura del módulo

```
digitalizacion/
│
├── __init__.py
├── __manifest__.py                 # Metadatos, dependencias, archivos del módulo
│
├── models/
│   ├── __init__.py
│   ├── etapa.py                    # digitalizacion.etapa
│   ├── tipo_escaner.py             # digitalizacion.tipo_escaner
│   ├── proyecto.py                 # digitalizacion.proyecto
│   ├── asignacion.py               # digitalizacion.asignacion
│   ├── miembro_proyecto.py         # digitalizacion.miembro_proyecto
│   └── registro.py                 # digitalizacion.registro
│
├── controllers/
│   ├── __init__.py
│   └── portal.py                   # Rutas HTTP del portal del líder
│
├── views/
│   ├── admin/
│   │   ├── proyecto_views.xml
│   │   ├── asignacion_views.xml
│   │   └── menu_views.xml
│   ├── operaciones/
│   │   ├── miembro_views.xml
│   │   ├── registro_views.xml
│   │   └── menu_operaciones.xml
│   ├── configuracion/
│   │   ├── etapa_views.xml
│   │   ├── tipo_escaner_views.xml
│   │   └── menu_configuracion.xml
│   ├── portal/
│   │   ├── portal_home.xml
│   │   ├── portal_proyecto.xml
│   │   ├── portal_registro_form.xml
│   │   └── portal_miembros.xml
│   └── dashboard/
│       ├── dashboard_views.xml
│       └── dashboard_kpi.xml
│
├── security/
│   ├── ir.model.access.csv         # Permisos CRUD por grupo
│   └── security.xml                # Grupos y reglas de registro (ir.rule)
│
├── wizard/
│   ├── __init__.py
│   ├── cambio_etapa_wizard.py      # Cambio masivo de etapa de registros
│   └── asignacion_rapida_wizard.py # Asignación rápida de digitalizador
│
└── data/
    └── etapas_default.xml          # Datos iniciales: etapas del proceso
```

---

## 12. Seguridad y control de acceso

### Grupos definidos

```xml
<!-- security/security.xml -->
<record id="group_digitalizacion_admin" model="res.groups">
    <field name="name">Admin</field>
    <field name="category_id" ref="base.module_category_hidden"/>
</record>

<record id="group_digitalizacion_lider" model="res.groups">
    <field name="name">Líder (Portal)</field>
    <field name="category_id" ref="base.module_category_hidden"/>
</record>
```

### Permisos CRUD por modelo (`ir.model.access.csv`)

| Modelo | Grupo Admin | Grupo Líder |
|---|---|---|
| `digitalizacion.etapa` | CRUD completo | Solo lectura |
| `digitalizacion.tipo_escaner` | CRUD completo | Solo lectura |
| `digitalizacion.proyecto` | CRUD completo | Solo lectura |
| `digitalizacion.asignacion` | CRUD completo | Solo lectura |
| `digitalizacion.miembro_proyecto` | CRUD completo | Crear, leer, actualizar |
| `digitalizacion.registro` | CRUD completo | Crear, leer, actualizar |

### Cómo crear un usuario Líder (Portal) correctamente

> ⚠️ Los usuarios Portal en Odoo **no se crean desde Ajustes → Usuarios**.  
> Si se crean desde ahí quedan como Usuarios Internos y Odoo no permite que sean Portal también.

**Pasos correctos:**

1. Ir a **Contactos** → Crear nuevo contacto (nombre + correo)
2. En la ficha del contacto: **Acción ⚙️ → Otorgar acceso al portal**
3. Tildar "En el Portal" → **Aplicar**
4. Ir a **Ajustes → Usuarios y Empresas → Grupos**
5. Buscar **Digitalización / Líder (Portal)** → agregar el usuario en la pestaña Usuarios

---

## 15. Instalación del módulo

### Prerrequisitos

- Odoo 17 Community o Enterprise
- Python 3.10+
- PostgreSQL 14+
- Docker y Docker Compose (entorno recomendado)

### Con Docker (entorno de desarrollo)

```bash
# 1. Clonar el repositorio dentro de la carpeta de addons
git clone <repo-url> ./addons/digitalizacion

# 2. Levantar el entorno
docker compose up -d

# 3. Instalar el módulo desde la interfaz de Odoo
#    Ajustes → Activar modo desarrollador
#    Ajustes → Actualizar lista de apps → buscar "Digitalización" → Instalar

# 4. O instalar por línea de comandos
docker compose exec web odoo \
  -c /etc/odoo/odoo.conf \
  -i digitalizacion \
  -d nombre_base_de_datos \
  --stop-after-init
```

### Actualizar el módulo tras cambios

```bash
docker compose exec web odoo \
  -c /etc/odoo/odoo.conf \
  -u digitalizacion \
  -d digitalizacion_dev \
  --stop-after-init
```

### Configuración inicial post-instalación

1. Ir a **Digitalización → Configuración → Etapas** y verificar las etapas cargadas por defecto.
2. Ir a **Digitalización → Configuración → Tipos de Escáner** y agregar los equipos de la empresa.
3. Crear los contactos de los digitalizadores en **Contactos**.
4. Crear usuarios Líderes siguiendo el proceso de usuario Portal (ver [Sección 12](#12-seguridad-y-control-de-acceso)).
5. Crear el primer proyecto desde **Digitalización → Operaciones → Proyectos**.

---

## 16. Consideraciones técnicas

### Separación estricta Admin / Portal
El módulo mantiene separación total entre el backend (Admin) y el portal (Líder). Los controllers validan permisos en cada petición HTTP — no se confía únicamente en las reglas de registro de Odoo para el portal.

### Usuarios Portal vs Internos
Los usuarios Líder **deben crearse como usuarios Portal** desde Contactos → Otorgar acceso al portal. Crearlos directamente desde Ajustes → Usuarios los registra como Internos y Odoo no permite que sean Portal simultáneamente.

### Campos compute con `store=True`
El campo `progreso` del proyecto usa `store=True` para que sea consultable desde búsquedas y vistas de lista sin recalcular en tiempo real en cada carga.

### Constraints a nivel Python + SQL
Las validaciones críticas (líder único por proyecto, miembro único por proyecto) se implementan como `@api.constrains` en Python. Para mayor robustez se recomienda agregar también restricciones `_sql_constraints` en los modelos correspondientes.

### Dockerización del entorno
El módulo fue desarrollado en un entorno Dockerizado para garantizar consistencia de versiones de Odoo, Python y PostgreSQL entre desarrollo y producción. El `docker-compose.yml` debe especificar la versión exacta de la imagen Odoo.

---

## 17. Autora

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
