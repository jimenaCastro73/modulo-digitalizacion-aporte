# -*- coding: utf-8 -*-
import json
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "digitalizacion")
class TestDigitalizacionPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        """Uso de setUpClass para eficiencia (se ejecuta una vez)"""
        super(TestDigitalizacionPortal, cls).setUpClass()

        # 1. Referencias a grupos
        cls.grupo_lider = cls.env.ref("digitalizacion.group_digitalizacion_lider")
        cls.grupo_portal = cls.env.ref("base.group_portal")

        # 2. Usuarios con logins únicos para evitar choques en DB de desarrollo
        cls.user_lider = cls.env["res.users"].search(
            [("login", "=", "lider_http_test")], limit=1
        )
        if not cls.user_lider:
            cls.user_lider = cls.env["res.users"].create(
                {
                    "name": "Lider Test HTTP",
                    "login": "lider_http_test",
                    "password": "password123",
                    "groups_id": [(6, 0, [cls.grupo_portal.id, cls.grupo_lider.id])],
                }
            )

        cls.user_normal = cls.env["res.users"].search(
            [("login", "=", "normal_http_test")], limit=1
        )
        if not cls.user_normal:
            cls.user_normal = cls.env["res.users"].create(
                {
                    "name": "User Normal",
                    "login": "normal_http_test",
                    "password": "password123",
                    "groups_id": [(6, 0, [cls.grupo_portal.id])],
                }
            )

        # 3. Datos de negocio: PROYECTO
        cls.proyecto = cls.env["digitalizacion.proyecto"].create(
            {"name": "PROYECTO PORTAL TEST", "state": "en_curso"}
        )

        # 4. ETAPA: BUSCAR O CREAR (Aquí estaba el error)
        # Buscamos si ya existe "Limpieza", si no, la creamos.
        Etapa = cls.env["digitalizacion.etapa"]
        cls.etapa = Etapa.search([("name", "=", "Limpieza")], limit=1)
        if not cls.etapa:
            cls.etapa = Etapa.create({"name": "Limpieza"})

        # 5. Miembro
        cls.miembro_lider = cls.env["digitalizacion.miembro_proyecto"].create(
            {
                "proyecto_id": cls.proyecto.id,
                "partner_id": cls.user_lider.partner_id.id,
                "es_lider": True,
            }
        )
        cls.proyecto.write({"state": "en_curso"})

    def test_01_dashboard_acceso_permitido(self):
        """Verifica acceso exitoso del líder"""
        self.authenticate(self.user_lider.login, "password123")
        response = self.url_open("/digitalizacion/v1/dashboard")

        self.assertEqual(response.status_code, 200, "El dashboard debería cargar")

        # En lugar de buscar el nombre, buscamos el ID del proyecto
        # que sabemos que aparece en los inputs del HTML (visto en el log: value="581")
        self.assertIn(
            str(self.proyecto.id),
            response.text,
            "El ID del proyecto debe estar en el HTML",
        )

        # También buscamos el título que confirmamos que existe en tu HTML
        self.assertIn(
            "Panel de Control", response.text, "El título del panel debe ser visible"
        )

    def test_02_dashboard_acceso_denegado(self):
        """Verifica que el sistema redirige al login si no tiene el grupo"""
        # Forzamos logout para limpiar sesiones previas del puerto
        self.url_open("/web/session/logout")

        self.authenticate(self.user_normal.login, "password123")

        # allow_redirects=False nos permite ver el código 302 (Redirección)
        response = self.url_open("/digitalizacion/v1/dashboard", allow_redirects=False)

        # Si tu controlador hace request.redirect('/web/login'), el status es 302
        self.assertIn(response.status_code, [302, 303])
        self.assertIn("/web/login", response.headers.get("Location", ""))

    def test_03_api_guardar_registros_json(self):
        """Prueba integración con el componente OWL"""
        self.authenticate(self.user_lider.login, "password123")

        url = f"/digitalizacion/api/v1/proyectos/{self.proyecto.id}/registros"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",  # Estándar de Odoo
            "params": {
                "fecha": "2024-05-20",
                "registros": [
                    {
                        "miembro_id": self.miembro_lider.id,
                        "etapa_id": self.etapa.id,
                        "no_expedientes": 10,
                        "total_folios": 100,
                    }
                ],
            },
        }

        response = self.url_open(
            url, data=json.dumps(payload), headers={"Content-Type": "application/json"}
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        # Odoo 17 JSON-RPC devuelve el resultado dentro de 'result'
        result = data.get("result", {})

        self.assertTrue(
            result.get("success"),
            f"Error en API: {result.get('error') or data.get('error')}",
        )
