import tempfile
import unittest
from pathlib import Path

from lab4_sdn import FloodlightClient, Lab4SDNApp


class FakeController(FloodlightClient):
    def __init__(self):
        self.pushed = []
        self.deleted = []

    def get_attachment_point(self, *, mac=None, ip=None):
        if mac == "00:44:11:22:44:a7":
            return {"switch": "00:00:00:00:00:00:00:01", "port": "1"}
        return {"switch": "00:00:00:00:00:00:00:02", "port": "2"}

    def get_route(self, src_switch, src_port, dst_switch, dst_port):
        return [
            {"switch": src_switch, "port": src_port},
            {"switch": src_switch, "port": "3"},
            {"switch": dst_switch, "port": "4"},
            {"switch": dst_switch, "port": dst_port},
        ]

    def push_flow(self, flow):
        self.pushed.append(flow)

    def delete_flow(self, name):
        self.deleted.append(name)


class Lab4SDNTests(unittest.TestCase):
    def setUp(self):
        self.controller = FakeController()
        self.app = Lab4SDNApp(controller=self.controller)
        self.app.import_from_yaml("sample_data.yaml")

    def test_import_and_authorization(self):
        alumno = self.app.get_alumno("20012482")
        servidor = self.app.get_servidor("Servidor 1")
        self.assertTrue(self.app.esta_autorizado(alumno, servidor, servidor.servicios["ssh"]))

    def test_reject_unauthorized_connection(self):
        with self.assertRaisesRegex(ValueError, "not authorized"):
            self.app.create_connection("20080621", "Servidor 1", "ssh")

    def test_create_and_delete_connection(self):
        conexion = self.app.create_connection("20012482", "Servidor 1", "ssh")
        self.assertEqual(conexion.handler, "H001")
        self.assertEqual(len(conexion.flow_names), 8)
        self.assertEqual(len(self.controller.pushed), 8)

        warnings = self.app.delete_connection("H001")
        self.assertEqual(warnings, [])
        self.assertEqual(self.controller.deleted, conexion.flow_names)

    def test_reverse_flows_use_inverse_ports(self):
        self.app.create_connection("20012482", "Servidor 1", "ssh")
        reverse_flows = [flow for flow in self.controller.pushed if "_rev_" in flow["name"] and "arp" not in flow["name"]]
        reverse_arp_flows = [flow for flow in self.controller.pushed if "_arp_rev_" in flow["name"]]

        self.assertEqual(reverse_flows[0]["in_port"], "3")
        self.assertEqual(reverse_flows[0]["actions"], "output=1")
        self.assertEqual(reverse_flows[1]["in_port"], "2")
        self.assertEqual(reverse_flows[1]["actions"], "output=4")

        self.assertEqual(reverse_arp_flows[0]["in_port"], "3")
        self.assertEqual(reverse_arp_flows[0]["actions"], "output=1")
        self.assertEqual(reverse_arp_flows[1]["in_port"], "2")
        self.assertEqual(reverse_arp_flows[1]["actions"], "output=4")

    def test_add_missing_student_rejected(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            self.app.add_alumno_to_curso("TEL354", "99999999")

    def test_export_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "export.yaml"
            self.app.export_to_yaml(str(target))

            fresh = Lab4SDNApp(controller=self.controller)
            fresh.import_from_yaml(str(target))
            self.assertEqual(sorted(fresh.alumnos_by_codigo), sorted(self.app.alumnos_by_codigo))
            self.assertEqual(sorted(fresh.cursos_by_codigo), sorted(self.app.cursos_by_codigo))


if __name__ == "__main__":
    unittest.main()
