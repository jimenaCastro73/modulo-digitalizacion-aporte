# -*- coding: utf-8 -*-
"""
tests/ — Suite de pruebas para el módulo digitalizacion

Archivos:
  test_registro_unitario.py  → Pruebas unitarias (caja blanca) sobre constraints,
                               computed fields y validaciones del modelo registro.
  test_registro_regresion.py → Pruebas de regresión (caja negra) sobre flujos CRUD
                               completos y validaciones de integridad.
  test_proyecto_unitario.py  → Pruebas unitarias sobre el modelo proyecto.
  test_miembro_unitario.py   → Pruebas unitarias sobre miembro_proyecto.
"""

from . import test_registro_unitario  # noqa: F401
from . import test_registro_regresion  # noqa: F401
from . import test_proyecto_unitario  # noqa: F401
from . import test_miembro_unitario  # noqa: F401
