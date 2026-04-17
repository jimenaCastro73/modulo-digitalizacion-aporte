# -*- coding: utf-8 -*-
import time
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "digitalizacion")
class TestDigitalizacionV2(TransactionCase):
    def setUp(self):
        super(TestDigitalizacionV2, self).setUp()

        # 1. Etapas - BUSCAR las reales
        Etapa = self.env["digitalizacion.etapa"]

        self.etapa_limpieza = Etapa.search([("name", "=", "Limpieza")], limit=1)
        if not self.etapa_limpieza:
            self.skipTest("La etapa 'Limpieza' no existe")

        self.etapa_digitalizado = Etapa.search([("name", "=", "Digitalizado")], limit=1)
        if not self.etapa_digitalizado:
            self.skipTest("La etapa 'Digitalizado' no existe")

        # Opcional: si existen, las usamos; si no, las creamos temporalmente
        self.etapa_ordenado = Etapa.search([("name", "=", "Ordenado")], limit=1)
        self.etapa_editado = Etapa.search([("name", "=", "Editado")], limit=1)
        self.etapa_indexado = Etapa.search([("name", "=", "Indexado")], limit=1)

        # 2. Usuarios Líderes
        ResUsers = self.env["res.users"]
        grupo_lider = self.env.ref("digitalizacion.group_digitalizacion_lider")

        self.user_lider_a = ResUsers.search([("login", "=", "lider_a_test")], limit=1)
        if not self.user_lider_a:
            self.user_lider_a = ResUsers.create(
                {
                    "name": "Líder Proyecto A",
                    "login": "lider_a_test",
                    "groups_id": [
                        (6, 0, [self.env.ref("base.group_portal").id, grupo_lider.id])
                    ],
                }
            )

        self.user_lider_b = ResUsers.search([("login", "=", "lider_b_test")], limit=1)
        if not self.user_lider_b:
            self.user_lider_b = ResUsers.create(
                {
                    "name": "Líder Proyecto B",
                    "login": "lider_b_test",
                    "groups_id": [
                        (6, 0, [self.env.ref("base.group_portal").id, grupo_lider.id])
                    ],
                }
            )

        # 3. Proyectos
        timestamp = str(int(time.time()))

        self.proyecto_a = self.env["digitalizacion.proyecto"].create(
            {"name": f"PROY_TEST_ALFA_{timestamp}"}
        )

        self.proyecto_b = self.env["digitalizacion.proyecto"].create(
            {"name": f"PROY_TEST_BETA_{timestamp}"}
        )

        # 4. Miembros
        self.partner_juan = self.env["res.partner"].create(
            {"name": f"Juan Operador TEST {timestamp}"}
        )
        self.partner_pedro = self.env["res.partner"].create(
            {"name": f"Pedro Operador TEST {timestamp}"}
        )

        self.miembro_a = self.env["digitalizacion.miembro_proyecto"].create(
            {"proyecto_id": self.proyecto_a.id, "partner_id": self.partner_juan.id}
        )

        self.miembro_b = self.env["digitalizacion.miembro_proyecto"].create(
            {"proyecto_id": self.proyecto_b.id, "partner_id": self.partner_pedro.id}
        )

        # 5. Asignaciones
        self.env["digitalizacion.asignacion"].create(
            {"lider_id": self.user_lider_a.id, "proyecto_id": self.proyecto_a.id}
        )
        self.env["digitalizacion.asignacion"].create(
            {"lider_id": self.user_lider_b.id, "proyecto_id": self.proyecto_b.id}
        )

    def tearDown(self):
        super(TestDigitalizacionV2, self).tearDown()

    # TEST 1: Limpieza - compute produccion_principal
    def test_01_limpieza_compute_produccion_principal(self):
        """Limpieza: produccion_principal = no_expedientes"""
        Registro = self.env["digitalizacion.registro"]
        reg = Registro.create(
            {
                "lider_id": self.user_lider_a.id,
                "proyecto_id": self.proyecto_a.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_limpieza.id,
                "no_expedientes": 45,
                "total_folios": 1200,
            }
        )
        self.assertEqual(reg.produccion_principal, 45)
        self.assertEqual(reg.unidad_produccion, "expedientes")

    # TEST 2: Digitalizado - compute y validación de escáner
    def test_02_digitalizado_compute_y_escaner(self):
        """Digitalizado: produccion_principal = total_escaneos"""
        Registro = self.env["digitalizacion.registro"]

        # Test compute
        reg = Registro.create(
            {
                "lider_id": self.user_lider_a.id,
                "proyecto_id": self.proyecto_a.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_digitalizado.id,
                "total_escaneos": 150,
                "tipo_escaner_ids": [(6, 0, [])],  # Vacío a propósito para test
            }
        )
        self.assertEqual(reg.produccion_principal, 150)
        self.assertEqual(reg.unidad_produccion, "escaneos")

    # TEST 3: Editado (si existe) - usa total_folios
    def test_03_editado_compute_produccion_principal(self):
        """Editado: produccion_principal = total_folios (folios editados)"""
        if not self.etapa_editado:
            self.skipTest("La etapa 'Editado' no existe, test saltado")

        Registro = self.env["digitalizacion.registro"]
        reg = Registro.create(
            {
                "lider_id": self.user_lider_a.id,
                "proyecto_id": self.proyecto_a.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_editado.id,
                "total_folios": 250,
                "referencia_cajas": "BF202, BF199",
            }
        )
        self.assertEqual(reg.produccion_principal, 250)
        self.assertEqual(reg.unidad_produccion, "folios")

    # TEST 4: Indexado (si existe) - usa folios_indexados
    def test_04_indexado_compute_produccion_principal(self):
        """Indexado: produccion_principal = folios_indexados"""
        if not self.etapa_indexado:
            self.skipTest("La etapa 'Indexado' no existe, test saltado")

        Registro = self.env["digitalizacion.registro"]
        reg = Registro.create(
            {
                "lider_id": self.user_lider_a.id,
                "proyecto_id": self.proyecto_a.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_indexado.id,
                "folios_indexados": 320,
                "expedientes_indexados": 12,
            }
        )
        self.assertEqual(reg.produccion_principal, 320)
        self.assertEqual(reg.unidad_produccion, "folios")

    # TEST 5: Validación API con datos basura
    def test_05_validar_fila_api_basura(self):
        Registro = self.env["digitalizacion.registro"]
        fila_erronea = {
            "miembro_id": self.miembro_a.id,
            "etapa_id": self.etapa_limpieza.id,
            "no_expedientes": "esto_no_es_un_numero",
        }
        with self.assertRaises(ValidationError):
            Registro.validar_fila_api(fila_erronea, 1)

    # TEST 6: Seguridad - aislamiento entre líderes
    def test_06_seguridad_aislamiento_lideres(self):
        Registro = self.env["digitalizacion.registro"]

        reg_privado = Registro.create(
            {
                "lider_id": self.user_lider_b.id,
                "proyecto_id": self.proyecto_b.id,
                "miembro_id": self.miembro_b.id,
                "etapa_id": self.etapa_limpieza.id,
            }
        )

        registros_visibles = Registro.with_user(self.user_lider_a).search([])
        self.assertNotIn(
            reg_privado.id,
            registros_visibles.ids,
            "ERROR: Líder A puede ver registros del Líder B",
        )

    # TEST 7: Restricción de fechas en proyecto
    def test_07_constrains_fechas_proyecto(self):
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.proyecto"].create(
                {
                    "name": f"Proyecto Invalido_{int(time.time())}",
                    "fecha_inicio": "2026-05-01",
                    "fecha_fin_estimada": "2026-01-01",
                }
            )

    # TEST 8: Restricción - miembro debe pertenecer al proyecto
    def test_08_constrains_miembro_pertenece_proyecto(self):
        Registro = self.env["digitalizacion.registro"]
        with self.assertRaises(ValidationError):
            Registro.create(
                {
                    "lider_id": self.user_lider_a.id,
                    "proyecto_id": self.proyecto_a.id,
                    "miembro_id": self.miembro_b.id,  # Miembro del proyecto B
                    "etapa_id": self.etapa_limpieza.id,
                }
            )

    # TEST 9: Ordenado (si existe) - similar a Limpieza
    def test_09_ordenado_compute_produccion_principal(self):
        """Ordenado: produccion_principal = no_expedientes"""
        if not self.etapa_ordenado:
            self.skipTest("La etapa 'Ordenado' no existe, test saltado")

        Registro = self.env["digitalizacion.registro"]
        reg = Registro.create(
            {
                "lider_id": self.user_lider_a.id,
                "proyecto_id": self.proyecto_a.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_ordenado.id,
                "no_expedientes": 30,
                "total_folios": 800,
            }
        )
        self.assertEqual(reg.produccion_principal, 30)
        self.assertEqual(reg.unidad_produccion, "expedientes")

    # TEST 10: Asignación automática de grupo líder
    def test_10_asignacion_automatica_grupo_lider(self):
        """Al marcar es_lider=True, se asigna automáticamente el grupo líder al usuario portal"""
        # Crear un partner y su usuario portal
        partner = self.env["res.partner"].create(
            {"name": f"Nuevo Líder TEST {int(time.time())}"}
        )

        usuario_portal = self.env["res.users"].create(
            {
                "name": partner.name,
                "login": f"lider_test_{int(time.time())}",
                "partner_id": partner.id,
                "share": True,  # Usuario portal
                "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )

        # Crear miembro sin líder
        miembro = self.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": self.proyecto_a.id,
                "partner_id": partner.id,
                "es_lider": False,
            }
        )

        grupo_lider = self.env.ref("digitalizacion.group_digitalizacion_lider")
        self.assertNotIn(grupo_lider, usuario_portal.groups_id)

        # Marcar como líder
        miembro.write({"es_lider": True})

        # Verificar que se asignó el grupo
        self.assertIn(grupo_lider, usuario_portal.groups_id)

        # Desmarcar como líder
        miembro.write({"es_lider": False})

        # Verificar que se removió el grupo (ya que no es líder en otros proyectos)
        self.assertNotIn(grupo_lider, usuario_portal.groups_id)
