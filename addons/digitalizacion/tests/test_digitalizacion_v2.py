# -*- coding: utf-8 -*-
import time
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "digitalizacion")
class TestDigitalizacionV2(TransactionCase):
    def setUp(self):
        super(TestDigitalizacionV2, self).setUp()

        # 1. Etapas - BUSCAR las reales (NO CREAR)
        Etapa = self.env["digitalizacion.etapa"]

        # Buscar etapa "Limpieza" (debe existir en la BD por los datos demo/XML)
        self.etapa_limpieza = Etapa.search([("name", "=", "Limpieza")], limit=1)
        if not self.etapa_limpieza:
            self.skipTest("La etapa 'Limpieza' no existe en la base de datos")

        # Buscar etapa "Digitalizado"
        self.etapa_digitalizado = Etapa.search([("name", "=", "Digitalizado")], limit=1)
        if not self.etapa_digitalizado:
            self.skipTest("La etapa 'Digitalizado' no existe en la base de datos")

        # 2. Usuarios Líderes - BUSCAR o CREAR con cleanup
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

        # 3. Proyectos - usar nombres únicos por timestamp para evitar conflictos
        import time

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
        """Limpia los datos creados por el test"""
        # Eliminar en orden inverso por dependencias
        self.env["digitalizacion.registro"].search([]).unlink()
        self.env["digitalizacion.asignacion"].search([]).unlink()
        self.env["digitalizacion.miembro_proyecto"].search([]).unlink()
        self.env["digitalizacion.proyecto"].search(
            [("name", "like", "PROY_TEST_%")]
        ).unlink()
        self.env["res.partner"].search([("name", "like", "%TEST%")]).unlink()
        self.env["res.users"].search(
            [("login", "in", ["lider_a_test", "lider_b_test"])]
        ).unlink()
        super(TestDigitalizacionV2, self).tearDown()

    # PILAR A: Lógica de Computes
    def test_A_compute_produccion_principal(self):
        Registro = self.env["digitalizacion.registro"]
        reg = Registro.create(
            {
                "lider_id": self.user_lider_a.id,
                "proyecto_id": self.proyecto_a.id,
                "miembro_id": self.miembro_a.id,
                "etapa_id": self.etapa_limpieza.id,
                "no_expedientes": 45,
            }
        )
        self.assertEqual(reg.produccion_principal, 45)

    # PILAR B: Validación API
    def test_B_validar_fila_api_basura(self):
        Registro = self.env["digitalizacion.registro"]
        fila_erronea = {
            "miembro_id": self.miembro_a.id,
            "etapa_id": self.etapa_limpieza.id,
            "no_expedientes": "esto_no_es_un_numero",
        }
        with self.assertRaises(ValidationError):
            Registro.validar_fila_api(fila_erronea, 1)

    # PILAR C: Seguridad (ir.rule)
    def test_C_seguridad_aislamiento_lideres(self):
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

    # PILAR D: Restricciones de Modelo
    def test_D_constrains_fechas_y_permisos(self):
        with self.assertRaises(ValidationError):
            self.env["digitalizacion.proyecto"].create(
                {
                    "name": f"Proyecto Invalido_{int(time.time())}",
                    "fecha_inicio": "2026-05-01",
                    "fecha_fin_estimada": "2026-01-01",
                }
            )
