# 📊 Especificación de Dashboards — Módulo de Digitalización
### Referencia técnica para implementación | Días 35-37 del roadmap

> Basado en el formato real de trabajo del Proyecto Inprema (Excel agosto 2025).  
> Cada registro = 1 digitalizador + 1 día + producción desglosada por tipo.

---

## Campos reales del registro (`digitalizacion.registro`)

Antes de los dashboards, el modelo debe tener estos campos confirmados:

| Campo | Tipo Odoo | Descripción | Viene del Excel |
|---|---|---|---|
| `miembro_id` | Many2one | Digitalizador | NOMBRE |
| `fecha` | Date | Fecha del registro | FECHA |
| `no_caja` | Char | Número(s) de caja procesada | No DE CAJA |
| `no_expedientes` | Integer | Expedientes del día | No expedientes |
| `total_folios` | Integer | Hojas físicas procesadas | TOTAL FOLIOS (Hojas físicas) |
| `total_escaneos` | Integer | Hojas digitalizadas | TOTAL ESCANEOS (hojas digital) |
| `tipo_escaner_id` | Many2one | Escáner utilizado | Tipo de escaner |
| `expedientes_indexados` | Integer | Expedientes indexados | Expedientes indexados |
| `folios_indexados` | Integer | Folios indexados | Folios indexados |
| `observacion` | Text | Notas del registro | OBSERVACION |
| `proyecto_id` | Many2one | Proyecto al que pertenece | — |
| `lider_id` | Many2one | Líder que registró | — |

---

## Dashboard 1 — Admin (Backoffice)

**Archivo:** `views/dashboard/dashboard_admin.xml`  
**Modelo base:** `digitalizacion.registro` + `digitalizacion.proyecto`  
**Acceso:** Solo grupo `Digitalización / Admin`

---

### Sección A — KPIs del mes (tarjetas superiores)

Inspirado directamente en los totales del Excel:

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ESCANEOS       │ │  FOLIOS         │ │  EXPEDIENTES    │ │  FOLIOS         │
│  GLOBAL MES     │ │  FÍSICOS MES    │ │  INDEXADOS MES  │ │  INDEXADOS MES  │
│                 │ │                 │ │                 │ │                 │
│   901,295       │ │   208,390       │ │    3,959        │ │   239,927       │
│  hojas digital  │ │  hojas físicas  │ │  expedientes    │ │  folios         │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

| KPI | Campo fuente | Cálculo | Color sugerido |
|---|---|---|---|
| Escaneos Global Mes | `total_escaneos` | `SUM` filtrado por mes actual | Naranja `#FF8C00` |
| Folios Físicos Mes | `total_folios` | `SUM` filtrado por mes actual | Amarillo `#FFD700` |
| Expedientes Indexados Mes | `expedientes_indexados` | `SUM` filtrado por mes actual | Verde `#70AD47` |
| Folios Indexados Mes | `folios_indexados` | `SUM` filtrado por mes actual | Cyan `#00BCD4` |

**Implementación en Odoo (campo compute en modelo o `read_group` en controller):**

```python
# En el controller del dashboard o en un modelo transitorio
def _get_kpis_mes(self, proyecto_id=None):
    hoy = fields.Date.today()
    domain = [
        ('fecha', '>=', hoy.replace(day=1)),
        ('fecha', '<=', hoy),
    ]
    if proyecto_id:
        domain.append(('proyecto_id', '=', proyecto_id))

    registros = self.env['digitalizacion.registro'].read_group(
        domain=domain,
        fields=[
            'total_escaneos:sum',
            'total_folios:sum',
            'expedientes_indexados:sum',
            'folios_indexados:sum',
        ],
        groupby=[]
    )
    return registros[0] if registros else {}
```

---

### Sección B — Progreso por proyecto

```
PROYECTO INPREMA          ████████████████████░░░░░  78%   901,295 / 1,150,000 escaneos
PROYECTO XYZ              ████████░░░░░░░░░░░░░░░░░  32%   145,000 / 450,000 escaneos
```

| Elemento | Fuente |
|---|---|
| Nombre del proyecto | `digitalizacion.proyecto.name` |
| Barra de progreso | `progreso` (campo compute del proyecto) |
| Escaneos acumulados | `SUM(registro_ids.total_escaneos)` |
| Meta | `meta_escaneos` del proyecto |

**Vista Odoo sugerida:** `graph` view con `type="pie"` o barra de progreso custom en QWeb.

---

### Sección C — Producción por digitalizador (tabla + gráfica de barras)

Replica la columna NOMBRE del Excel pero con totales acumulados:

| Digitalizador | Escaneos mes | Folios físicos | Exp. indexados | Folios indexados |
|---|---|---|---|---|
| YADIRA | 225,409 | 208,390 | — | — |
| MARIO | 89,234 | 67,100 | 3,959 | 239,927 |
| ARNOL | 201,450 | 180,200 | — | — |
| EDWIN | 45,000 | 42,000 | — | — |
| LOURDES | 340,202 | 310,000 | — | — |

**Implementación:**

```python
# read_group agrupado por miembro
self.env['digitalizacion.registro'].read_group(
    domain=[('proyecto_id', '=', proyecto_id),
            ('fecha', '>=', primer_dia_mes)],
    fields=[
        'miembro_id',
        'total_escaneos:sum',
        'total_folios:sum',
        'expedientes_indexados:sum',
        'folios_indexados:sum',
    ],
    groupby=['miembro_id']
)
```

**Vista Odoo:** `graph` view con `type="bar"` agrupando por `miembro_id`, midiendo `total_escaneos`.

```xml
<record id="view_registro_graph_por_digitalizador" model="ir.ui.view">
    <field name="name">digitalizacion.registro.graph.digitalizador</field>
    <field name="model">digitalizacion.registro</field>
    <field name="arch" type="xml">
        <graph type="bar" stacked="0">
            <field name="miembro_id" type="row"/>
            <field name="total_escaneos" type="measure"/>
            <field name="total_folios" type="measure"/>
            <field name="expedientes_indexados" type="measure"/>
        </graph>
    </field>
</record>
```

---

### Sección D — Producción por día (gráfica de tendencia)

Gráfica de línea: eje X = fecha, eje Y = total escaneos del día (todos los digitalizadores).

```
Escaneos/día
  45,000 │                    ╭────╮
  40,000 │               ╭───╯    ╰──╮
  35,000 │          ╭────╯            ╰──╮
  30,000 │     ╭────╯                     ╰──
         └────────────────────────────────────▶ días del mes
           1   4   7   10  13  16  19  22  25
```

```xml
<record id="view_registro_graph_tendencia" model="ir.ui.view">
    <field name="name">digitalizacion.registro.graph.tendencia</field>
    <field name="model">digitalizacion.registro</field>
    <field name="arch" type="xml">
        <graph type="line">
            <field name="fecha" type="row"/>
            <field name="total_escaneos" type="measure"/>
        </graph>
    </field>
</record>
```

---

### Sección E — Filtros del dashboard

```xml
<search>
    <filter name="este_mes" string="Este mes"
            domain="[('fecha', '>=', (context_today()).strftime('%Y-%m-01'))]"/>
    <filter name="mes_anterior" string="Mes anterior" .../>
    <group expand="0" string="Agrupar por">
        <filter name="por_proyecto" string="Proyecto" context="{'group_by': 'proyecto_id'}"/>
        <filter name="por_digitalizador" string="Digitalizador" context="{'group_by': 'miembro_id'}"/>
        <filter name="por_fecha" string="Fecha" context="{'group_by': 'fecha:month'}"/>
    </group>
</search>
```

---

## Dashboard 2 — Portal Líder (Website)

**Archivo:** `views/portal/portal_dashboard.xml`  
**Controller:** `/digitalizacion/proyecto/<id>/dashboard`  
**Acceso:** Solo el líder con asignación activa en ese proyecto  
**Scope:** Todo orientado al proyecto asignado del líder, equivalente al Admin pero filtrado

---

### Sección A — KPIs del mes de MI proyecto (tarjetas superiores)

Mismo layout que el Admin pero filtrado por `proyecto_id` del líder:

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  MIS ESCANEOS   │ │  FOLIOS         │ │  EXPEDIENTES    │ │  FOLIOS         │
│  DEL MES        │ │  FÍSICOS MES    │ │  INDEXADOS MES  │ │  INDEXADOS MES  │
│   225,409       │ │   208,390       │ │    3,959        │ │   239,927       │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

### Sección B — Progreso del proyecto

```
META: 1,150,000 escaneos
ACTUAL: 901,295 escaneos

[████████████████████░░░░░] 78.4%

Días restantes: 12 días hábiles
Promedio necesario por día: 20,725 escaneos/día
```

| Elemento | Cálculo |
|---|---|
| % progreso | `(total_escaneos_acumulados / meta_escaneos) * 100` |
| Días restantes | `(fecha_fin_estimada - hoy).days` |
| Promedio necesario | `(meta_escaneos - total_acumulado) / dias_restantes` |

---

### Sección C — Producción de HOY (registro del día actual)

Resumen rápido del día en curso — lo primero que ve el líder al abrir el portal:

```
📅 HOY: 01/08/2025

YADIRA          5,407 escaneos     3,835 folios    —
EDWIN           —                  —               limpieza expedientes
MARIO           —                  179 exp.        11,119 folios indexados
ARNOL           8,162 escaneos     7,450 folios    —
```

**Implementación en controller:**

```python
hoy = fields.Date.today()
registros_hoy = request.env['digitalizacion.registro'].search([
    ('proyecto_id', '=', proyecto_id),
    ('fecha', '=', hoy),
])
```

---

### Sección D — Producción por miembro (acumulado del mes)

Misma tabla que el Admin pero solo del proyecto del líder:

| Miembro | Escaneos mes | Folios físicos | Exp. indexados | Folios indexados |
|---|---|---|---|---|
| YADIRA | 225,409 | 208,390 | — | — |
| MARIO | 89,234 | 67,100 | 3,959 | 239,927 |
| ARNOL | 201,450 | 180,200 | — | — |

---

### Sección E — Mis registros recientes (tabla)

Los últimos 10-15 registros del proyecto ordenados por fecha descendente:

| Fecha | Miembro | Caja | Folios físicos | Escaneos | Tipo escáner | Observación |
|---|---|---|---|---|---|---|
| 04/08/2025 | YADIRA | BF193,216... | 3,835 | 3,327 | KYOCERA, CANON | Escaneo sin editar (exp dobles) |
| 04/08/2025 | MARIO | BF206,196... | — | — | — | Indexado expedientes |
| 01/08/2025 | ARNOL | BF195,196... | 7,450 | 8,162 | FUJITSU | Escaneo y editado |

**Template QWeb:**

```xml
<table class="table table-sm table-hover">
    <thead>
        <tr>
            <th>Fecha</th>
            <th>Miembro</th>
            <th>No. Caja</th>
            <th>Folios físicos</th>
            <th>Escaneos</th>
            <th>Escáner</th>
            <th>Observación</th>
        </tr>
    </thead>
    <tbody>
        <t t-foreach="registros_recientes" t-as="reg">
            <tr>
                <td><t t-esc="reg.fecha"/></td>
                <td><t t-esc="reg.miembro_id.name"/></td>
                <td><t t-esc="reg.no_caja"/></td>
                <td><t t-esc="reg.total_folios"/></td>
                <td><t t-esc="reg.total_escaneos"/></td>
                <td><t t-esc="reg.tipo_escaner_id.name"/></td>
                <td><t t-esc="reg.observacion"/></td>
            </tr>
        </t>
    </tbody>
</table>
```

---

## Comparativa Admin vs Portal Líder

| KPI / Elemento | Admin | Portal Líder |
|---|---|---|
| Escaneos globales del mes | ✅ Todos los proyectos | ✅ Solo su proyecto |
| Folios físicos del mes | ✅ Todos | ✅ Solo su proyecto |
| Expedientes indexados | ✅ Todos | ✅ Solo su proyecto |
| Folios indexados | ✅ Todos | ✅ Solo su proyecto |
| Progreso del proyecto | ✅ Todos los proyectos | ✅ Solo su proyecto |
| Producción por digitalizador | ✅ Todos | ✅ Solo su equipo |
| Producción por día (tendencia) | ✅ Todos | ✅ Solo su proyecto |
| Registros de hoy | ❌ | ✅ Vista rápida |
| Registros recientes (tabla) | ❌ (usa la vista lista de Odoo) | ✅ Tabla en portal |
| Filtro por proyecto | ✅ | ❌ (ya está filtrado) |
| Filtro por mes | ✅ | ✅ |

---

## Notas de implementación para el roadmap

### Día 35 — Estructura base del dashboard
- Crear `views/dashboard/dashboard_admin.xml` con las 4 tarjetas KPI (Sección A)
- Crear acción de ventana apuntando al dashboard
- Agregar al menú principal

### Día 36 — Gráficas
- Implementar `graph` view tipo `bar` para producción por digitalizador (Sección C)
- Implementar `graph` view tipo `line` para tendencia diaria (Sección D)
- Ambas vistas ya usan el ORM de Odoo nativo — no requieren código Python extra

### Día 37 — KPIs compute + filtros + portal
- Implementar los 4 campos compute de KPIs en el modelo o controller
- Agregar filtros de búsqueda por mes/proyecto (Sección E)
- Implementar dashboard del portal (Secciones A-E del Portal Líder)

---

*Referencia basada en: Conteo Diario de Escaneos "Proyecto Inprema" — Agosto 2025*  
*Última actualización: Día 32 — Sábado 14 de Marzo, 2026*
