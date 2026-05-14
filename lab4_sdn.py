import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    value = _strip_quotes(value)
    lowered = value.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def parse_simple_yaml(text: str) -> Any:
    """Parse a small YAML subset sufficient for this lab schema."""

    lines: List[Tuple[int, str]] = []
    for raw_line in text.splitlines():
        content = raw_line.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        stripped = content.strip()
        lines.append((indent, stripped))

    index = 0

    def parse_block(expected_indent: int) -> Any:
        nonlocal index
        container: Optional[Any] = None

        while index < len(lines):
            indent, stripped = lines[index]
            if indent < expected_indent:
                break
            if indent > expected_indent:
                raise ValueError(f"Invalid indentation near: {stripped}")

            if stripped.startswith("- "):
                if container is None:
                    container = []
                if not isinstance(container, list):
                    raise ValueError("Mixed list and mapping at same indentation level")

                item_text = stripped[2:].strip()
                index += 1

                if not item_text:
                    item = parse_block(expected_indent + 2)
                    container.append(item)
                    continue

                if ":" in item_text:
                    key, raw_value = item_text.split(":", 1)
                    key = key.strip()
                    raw_value = raw_value.strip()
                    item: Dict[str, Any] = {}
                    if raw_value:
                        item[key] = _parse_scalar(raw_value)
                    else:
                        item[key] = None

                    if index < len(lines) and lines[index][0] > expected_indent:
                        child = parse_block(expected_indent + 2)
                        if item[key] is None:
                            item[key] = child
                        elif isinstance(child, dict):
                            item.update(child)
                        else:
                            raise ValueError(f"Unexpected list continuation for key '{key}'")
                    elif item[key] is None:
                        item[key] = {}

                    container.append(item)
                    continue

                container.append(_parse_scalar(item_text))
                continue

            if container is None:
                container = {}
            if not isinstance(container, dict):
                raise ValueError("Mixed mapping and list at same indentation level")

            if ":" not in stripped:
                raise ValueError(f"Expected key/value pair near: {stripped}")

            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            index += 1

            if raw_value:
                container[key] = _parse_scalar(raw_value)
                continue

            if index < len(lines) and lines[index][0] > expected_indent:
                container[key] = parse_block(expected_indent + 2)
            else:
                container[key] = {}

        return container if container is not None else {}

    return parse_block(0)


def load_yaml_file(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
    except ModuleNotFoundError:
        loaded = parse_simple_yaml(text)

    if not isinstance(loaded, dict):
        raise ValueError("The YAML root must be a mapping")
    return loaded


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if any(ch in text for ch in [":", "#", '"', "'"]) or text.startswith(" ") or text.endswith(" "):
        return json.dumps(text)
    return text


def dump_yaml(data: Any, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(data, dict):
        lines: List[str] = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(dump_yaml(value, indent + 2))
            else:
                lines.append(f"{spaces}{key}: {yaml_scalar(value)}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{spaces}- {{}}")
                    continue
                first_key = next(iter(item))
                first_value = item[first_key]
                if isinstance(first_value, (dict, list)):
                    lines.append(f"{spaces}- {first_key}:")
                    lines.append(dump_yaml(first_value, indent + 4))
                else:
                    lines.append(f"{spaces}- {first_key}: {yaml_scalar(first_value)}")
                for key, value in list(item.items())[1:]:
                    if isinstance(value, (dict, list)):
                        lines.append(f"{spaces}  {key}:")
                        lines.append(dump_yaml(value, indent + 4))
                    else:
                        lines.append(f"{spaces}  {key}: {yaml_scalar(value)}")
            elif isinstance(item, list):
                lines.append(f"{spaces}-")
                lines.append(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{spaces}{yaml_scalar(data)}"


class Alumno:
    def __init__(self, codigo: str, nombre: str, mac: str):
        self.codigo = codigo
        self.nombre = nombre
        self.mac = mac


class Servicio:
    def __init__(self, nombre: str, protocolo: str, puerto: int):
        self.nombre = nombre
        self.protocolo = protocolo
        self.puerto = puerto


class Servidor:
    def __init__(self, nombre: str, ip: str, mac: Optional[str] = None, servicios: Optional[Dict[str, "Servicio"]] = None):
        self.nombre = nombre
        self.ip = ip
        self.mac = mac
        self.servicios = servicios or {}


class CursoServidorPermitido:
    def __init__(self, nombre: str, servicios_permitidos: Optional[List[str]] = None):
        self.nombre = nombre
        self.servicios_permitidos = servicios_permitidos or []


class Curso:
    def __init__(
        self,
        codigo: str,
        nombre: str,
        estado: str,
        alumnos: Optional[List[str]] = None,
        servidores_permitidos: Optional[Dict[str, "CursoServidorPermitido"]] = None,
    ):
        self.codigo = codigo
        self.nombre = nombre
        self.estado = estado
        self.alumnos = alumnos or []
        self.servidores_permitidos = servidores_permitidos or {}


class Conexion:
    def __init__(
        self,
        handler: str,
        codigo_alumno: str,
        nombre_servidor: str,
        nombre_servicio: str,
        ruta: List[Dict[str, Any]],
        flow_names: List[str],
    ):
        self.handler = handler
        self.codigo_alumno = codigo_alumno
        self.nombre_servidor = nombre_servidor
        self.nombre_servicio = nombre_servicio
        self.ruta = ruta
        self.flow_names = flow_names


class FloodlightClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str) -> Any:
        response = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        response = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.text.strip():
            return response.json()
        return {}

    def _delete(self, path: str, payload: Dict[str, Any]) -> Any:
        response = self.session.delete(
            f"{self.base_url}{path}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.text.strip():
            return response.json()
        return {}

    def get_attachment_point(self, *, mac: Optional[str] = None, ip: Optional[str] = None) -> Dict[str, Any]:
        if mac:
            data = self._get(f"/wm/device/?mac={mac}")
        elif ip:
            data = self._get(f"/wm/device/?ipv4={ip}")
        else:
            raise ValueError("Attachment point lookup requires mac or ip")

        devices = data.get("devices", []) if isinstance(data, dict) else data
        if not devices:
            raise ValueError("Device not found in controller inventory")

        device = devices[0]
        points = device.get("attachmentPoint") or []
        if not points:
            raise ValueError("Device does not have an attachment point")

        point = points[0]
        return {
            "switch": point.get("switchDPID") or point.get("switch"),
            "port": str(point.get("port")),
        }

    def get_route(self, src_switch: str, src_port: str, dst_switch: str, dst_port: str) -> List[Dict[str, Any]]:
        data = self._get(f"/wm/topology/route/{src_switch}/{src_port}/{dst_switch}/{dst_port}/json")
        if isinstance(data, dict) and "results" in data:
            route = data["results"]
        else:
            route = data
        if not route:
            raise ValueError("Controller did not return a route")
        return route

    def push_flow(self, flow: Dict[str, Any]) -> None:
        self._post("/wm/staticflowpusher/json", flow)

    def delete_flow(self, name: str) -> None:
        self._delete("/wm/staticflowpusher/json", {"name": name})


class Lab4SDNApp:
    def __init__(self, controller: Optional[FloodlightClient] = None):
        self.controller = controller or FloodlightClient()
        self.alumnos_by_codigo: Dict[str, Alumno] = {}
        self.alumnos_by_mac: Dict[str, Alumno] = {}
        self.cursos_by_codigo: Dict[str, Curso] = {}
        self.servidores_by_nombre: Dict[str, Servidor] = {}
        self.servidores_by_ip: Dict[str, Servidor] = {}
        self.conexiones_by_handler: Dict[str, Conexion] = {}
        self.handler_counter = 1

    def import_from_yaml(self, file_path: str) -> None:
        data = load_yaml_file(Path(file_path))
        alumnos = self._build_alumnos(data.get("alumnos", []))
        servidores = self._build_servidores(data.get("servidores", []))
        cursos = self._build_cursos(data.get("cursos", []), alumnos, servidores)

        self.alumnos_by_codigo = {item.codigo: item for item in alumnos.values()}
        self.alumnos_by_mac = {item.mac.lower(): item for item in alumnos.values()}
        self.servidores_by_nombre = {item.nombre: item for item in servidores.values()}
        self.servidores_by_ip = {item.ip: item for item in servidores.values()}
        self.cursos_by_codigo = {item.codigo: item for item in cursos.values()}
        self.conexiones_by_handler.clear()
        self.handler_counter = 1

    def export_to_yaml(self, file_path: str) -> None:
        data = {
            "alumnos": [
                {
                    "nombre": alumno.nombre,
                    "codigo": alumno.codigo,
                    "mac": alumno.mac,
                }
                for alumno in sorted(self.alumnos_by_codigo.values(), key=lambda x: x.codigo)
            ],
            "cursos": [
                {
                    "codigo": curso.codigo,
                    "estado": curso.estado,
                    "nombre": curso.nombre,
                    "alumnos": curso.alumnos,
                    "servidores": [
                        {
                            "nombre": servidor.nombre,
                            "servicios_permitidos": servidor.servicios_permitidos,
                        }
                        for servidor in curso.servidores_permitidos.values()
                    ],
                }
                for curso in sorted(self.cursos_by_codigo.values(), key=lambda x: x.codigo)
            ],
            "servidores": [
                {
                    "nombre": servidor.nombre,
                    "ip": servidor.ip,
                    "mac": servidor.mac,
                    "servicios": [
                        {
                            "nombre": servicio.nombre,
                            "protocolo": servicio.protocolo,
                            "puerto": servicio.puerto,
                        }
                        for servicio in servidor.servicios.values()
                    ],
                }
                for servidor in sorted(self.servidores_by_nombre.values(), key=lambda x: x.nombre)
            ],
        }
        Path(file_path).write_text(dump_yaml(data) + "\n", encoding="utf-8")

    def _build_alumnos(self, items: Any) -> Dict[str, Alumno]:
        if not isinstance(items, list):
            raise ValueError("The 'alumnos' block must be a list")
        result: Dict[str, Alumno] = {}
        macs: set[str] = set()
        for raw in items:
            alumno = Alumno(
                codigo=str(raw["codigo"]),
                nombre=str(raw["nombre"]),
                mac=str(raw["mac"]).lower(),
            )
            if alumno.codigo in result:
                raise ValueError(f"Duplicate alumno code: {alumno.codigo}")
            if alumno.mac in macs:
                raise ValueError(f"Duplicate alumno mac: {alumno.mac}")
            result[alumno.codigo] = alumno
            macs.add(alumno.mac)
        return result

    def _build_servidores(self, items: Any) -> Dict[str, Servidor]:
        if not isinstance(items, list):
            raise ValueError("The 'servidores' block must be a list")
        result: Dict[str, Servidor] = {}
        ips: set[str] = set()
        for raw in items:
            nombre = str(raw["nombre"])
            ip = str(raw["ip"])
            if nombre in result:
                raise ValueError(f"Duplicate servidor name: {nombre}")
            if ip in ips:
                raise ValueError(f"Duplicate servidor ip: {ip}")
            servicios_raw = raw.get("servicios", [])
            servicios: Dict[str, Servicio] = {}
            for srv in servicios_raw:
                servicio = Servicio(
                    nombre=str(srv["nombre"]),
                    protocolo=str(srv["protocolo"]).upper(),
                    puerto=int(srv["puerto"]),
                )
                servicios[servicio.nombre] = servicio
            result[nombre] = Servidor(
                nombre=nombre,
                ip=ip,
                mac=(str(raw["mac"]).lower() if raw.get("mac") else None),
                servicios=servicios,
            )
            ips.add(ip)
        return result

    def _build_cursos(
        self,
        items: Any,
        alumnos: Dict[str, Alumno],
        servidores: Dict[str, Servidor],
    ) -> Dict[str, Curso]:
        if not isinstance(items, list):
            raise ValueError("The 'cursos' block must be a list")
        result: Dict[str, Curso] = {}
        for raw in items:
            codigo = str(raw["codigo"])
            alumnos_curso = [str(code) for code in raw.get("alumnos", [])]
            for code in alumnos_curso:
                if code not in alumnos:
                    raise ValueError(f"Curso {codigo} references missing alumno {code}")

            servidores_permitidos: Dict[str, CursoServidorPermitido] = {}
            for server_raw in raw.get("servidores", []):
                server_name = str(server_raw["nombre"])
                if server_name not in servidores:
                    raise ValueError(f"Curso {codigo} references missing servidor {server_name}")
                allowed = [str(name) for name in server_raw.get("servicios_permitidos", [])]
                for service_name in allowed:
                    if service_name not in servidores[server_name].servicios:
                        raise ValueError(
                            f"Curso {codigo} allows missing service {service_name} on servidor {server_name}"
                        )
                servidores_permitidos[server_name] = CursoServidorPermitido(
                    nombre=server_name,
                    servicios_permitidos=allowed,
                )

            result[codigo] = Curso(
                codigo=codigo,
                nombre=str(raw["nombre"]),
                estado=str(raw["estado"]).upper(),
                alumnos=alumnos_curso,
                servidores_permitidos=servidores_permitidos,
            )
        return result

    def _next_handler(self) -> str:
        handler = f"H{self.handler_counter:03d}"
        self.handler_counter += 1
        return handler

    def list_cursos(self) -> List[Curso]:
        return sorted(self.cursos_by_codigo.values(), key=lambda item: item.codigo)

    def get_curso(self, codigo: str) -> Curso:
        curso = self.cursos_by_codigo.get(codigo)
        if not curso:
            raise ValueError(f"Curso {codigo} not found")
        return curso

    def add_alumno_to_curso(self, curso_codigo: str, alumno_codigo: str) -> None:
        curso = self.get_curso(curso_codigo)
        if alumno_codigo not in self.alumnos_by_codigo:
            raise ValueError(f"Alumno {alumno_codigo} not found")
        if alumno_codigo in curso.alumnos:
            raise ValueError(f"Alumno {alumno_codigo} already belongs to curso {curso_codigo}")
        curso.alumnos.append(alumno_codigo)

    def remove_alumno_from_curso(self, curso_codigo: str, alumno_codigo: str) -> None:
        curso = self.get_curso(curso_codigo)
        if alumno_codigo not in curso.alumnos:
            raise ValueError(f"Alumno {alumno_codigo} is not enrolled in curso {curso_codigo}")
        curso.alumnos.remove(alumno_codigo)

    def list_alumnos(self, filtro: Optional[str] = None) -> List[Alumno]:
        values = sorted(self.alumnos_by_codigo.values(), key=lambda item: item.codigo)
        if not filtro:
            return values
        needle = filtro.lower()
        return [item for item in values if needle in item.codigo.lower() or needle in item.nombre.lower()]

    def get_alumno(self, codigo: str) -> Alumno:
        alumno = self.alumnos_by_codigo.get(codigo)
        if not alumno:
            raise ValueError(f"Alumno {codigo} not found")
        return alumno

    def list_servidores(self) -> List[Servidor]:
        return sorted(self.servidores_by_nombre.values(), key=lambda item: item.nombre)

    def get_servidor(self, nombre: str) -> Servidor:
        servidor = self.servidores_by_nombre.get(nombre)
        if not servidor:
            raise ValueError(f"Servidor {nombre} not found")
        return servidor

    def esta_autorizado(self, alumno: Alumno, servidor: Servidor, servicio: Servicio) -> bool:
        for curso in self.cursos_by_codigo.values():
            if curso.estado != "DICTANDO":
                continue
            if alumno.codigo not in curso.alumnos:
                continue
            allowed_server = curso.servidores_permitidos.get(servidor.nombre)
            if not allowed_server:
                continue
            if servicio.nombre in allowed_server.servicios_permitidos:
                return True
        return False

    def get_attachment_point(self, *, mac: Optional[str] = None, ip: Optional[str] = None) -> Dict[str, Any]:
        return self.controller.get_attachment_point(mac=mac, ip=ip)

    def get_route(self, src_switch: str, src_port: str, dst_switch: str, dst_port: str) -> List[Dict[str, Any]]:
        return self.controller.get_route(src_switch, src_port, dst_switch, dst_port)

    def create_connection(self, alumno_codigo: str, servidor_nombre: str, servicio_nombre: str) -> Conexion:
        alumno = self.get_alumno(alumno_codigo)
        servidor = self.get_servidor(servidor_nombre)
        servicio = servidor.servicios.get(servicio_nombre)
        if not servicio:
            raise ValueError(f"Servicio {servicio_nombre} not found on servidor {servidor.nombre}")
        if not self.esta_autorizado(alumno, servidor, servicio):
            raise ValueError(
                f"Alumno {alumno.codigo} is not authorized for {servicio.nombre} on {servidor.nombre}"
            )

        alumno_ap = self.get_attachment_point(mac=alumno.mac)
        if servidor.mac:
            servidor_ap = self.get_attachment_point(mac=servidor.mac)
        else:
            servidor_ap = self.get_attachment_point(ip=servidor.ip)
        ruta = self.get_route(alumno_ap["switch"], alumno_ap["port"], servidor_ap["switch"], servidor_ap["port"])

        handler = self._next_handler()
        flow_names = self.build_route(handler, ruta, alumno, servidor, servicio)
        conexion = Conexion(
            handler=handler,
            codigo_alumno=alumno.codigo,
            nombre_servidor=servidor.nombre,
            nombre_servicio=servicio.nombre,
            ruta=ruta,
            flow_names=flow_names,
        )
        self.conexiones_by_handler[handler] = conexion
        return conexion

    def list_conexiones(self) -> List[Conexion]:
        return sorted(self.conexiones_by_handler.values(), key=lambda item: item.handler)

    def delete_connection(self, handler: str) -> List[str]:
        conexion = self.conexiones_by_handler.get(handler)
        if not conexion:
            raise ValueError(f"Conexion {handler} not found")
        warnings: List[str] = []
        for flow_name in conexion.flow_names:
            try:
                self.controller.delete_flow(flow_name)
            except requests.RequestException as exc:
                warnings.append(f"Warning deleting {flow_name}: {exc}")
        del self.conexiones_by_handler[handler]
        return warnings

    def build_route(
        self,
        handler: str,
        ruta: List[Dict[str, Any]],
        alumno: Alumno,
        servidor: Servidor,
        servicio: Servicio,
    ) -> List[str]:
        if len(ruta) % 2 != 0:
            raise ValueError("Route length must be even: expected ingress/egress pairs")

        flow_names: List[str] = []
        path_segments = self._route_to_segments(ruta)
        protocol_value = "0x06" if servicio.protocolo.upper() == "TCP" else "0x11"
        transport_field = "tcp_dst" if servicio.protocolo.upper() == "TCP" else "udp_dst"
        reverse_transport_field = "tcp_src" if servicio.protocolo.upper() == "TCP" else "udp_src"

        for index, segment in enumerate(path_segments):
            dpid = segment["switch"]
            out_port = segment["out_port"]
            in_port = segment["in_port"]

            fwd_name = f"{handler}_fwd_{index}_{dpid.replace(':', '')}"
            rev_name = f"{handler}_rev_{index}_{dpid.replace(':', '')}"
            arp_fwd_name = f"{handler}_arp_fwd_{index}_{dpid.replace(':', '')}"
            arp_rev_name = f"{handler}_arp_rev_{index}_{dpid.replace(':', '')}"

            fwd_flow = {
                "switch": dpid,
                "name": fwd_name,
                "cookie": "0",
                "priority": "32768",
                "eth_type": "0x0800",
                "eth_src": alumno.mac,
                "eth_dst": servidor.mac or "",
                "ipv4_src": "0.0.0.0/0",
                "ipv4_dst": servidor.ip,
                "ip_proto": protocol_value,
                transport_field: str(servicio.puerto),
                "active": "true",
                "in_port": str(in_port),
                "actions": f"output={out_port}",
            }
            rev_flow = {
                "switch": dpid,
                "name": rev_name,
                "cookie": "0",
                "priority": "32768",
                "eth_type": "0x0800",
                "eth_src": servidor.mac or "",
                "eth_dst": alumno.mac,
                "ipv4_src": servidor.ip,
                "ipv4_dst": "0.0.0.0/0",
                "ip_proto": protocol_value,
                reverse_transport_field: str(servicio.puerto),
                "active": "true",
                "in_port": str(out_port),
                "actions": f"output={in_port}",
            }
            arp_fwd_flow = {
                "switch": dpid,
                "name": arp_fwd_name,
                "cookie": "0",
                "priority": "32767",
                "eth_type": "0x0806",
                "eth_src": alumno.mac,
                "active": "true",
                "in_port": str(in_port),
                "actions": f"output={out_port}",
            }
            arp_rev_flow = {
                "switch": dpid,
                "name": arp_rev_name,
                "cookie": "0",
                "priority": "32767",
                "eth_type": "0x0806",
                "eth_dst": alumno.mac,
                "active": "true",
                "in_port": str(out_port),
                "actions": f"output={in_port}",
            }

            for flow in (fwd_flow, rev_flow, arp_fwd_flow, arp_rev_flow):
                flow = {key: value for key, value in flow.items() if value != ""}
                self.controller.push_flow(flow)
                flow_names.append(flow["name"])

        return flow_names

    @staticmethod
    def _route_to_segments(route: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        segments = []
        for idx in range(0, len(route), 2):
            ingress = route[idx]
            egress = route[idx + 1]
            segments.append(
                {
                    "switch": ingress.get("switch") or ingress.get("switchDPID"),
                    "in_port": ingress.get("port"),
                    "out_port": egress.get("port"),
                }
            )
        return segments

    def print_cursos(self) -> None:
        for curso in self.list_cursos():
            print(f"{curso.codigo} | {curso.nombre} | {curso.estado}")

    def print_curso_detail(self, codigo: str) -> None:
        curso = self.get_curso(codigo)
        print(f"Codigo: {curso.codigo}")
        print(f"Nombre: {curso.nombre}")
        print(f"Estado: {curso.estado}")
        print("Alumnos:")
        for alumno_codigo in curso.alumnos:
            alumno = self.alumnos_by_codigo[alumno_codigo]
            print(f"  - {alumno.codigo} | {alumno.nombre}")
        print("Servidores permitidos:")
        for item in curso.servidores_permitidos.values():
            allowed = ", ".join(item.servicios_permitidos)
            print(f"  - {item.nombre}: {allowed}")

    def print_alumnos(self, filtro: Optional[str] = None) -> None:
        for alumno in self.list_alumnos(filtro):
            print(f"{alumno.codigo} | {alumno.nombre} | {alumno.mac}")

    def print_alumno_detail(self, codigo: str) -> None:
        alumno = self.get_alumno(codigo)
        print(f"Codigo: {alumno.codigo}")
        print(f"Nombre: {alumno.nombre}")
        print(f"MAC: {alumno.mac}")

    def print_servidores(self) -> None:
        for servidor in self.list_servidores():
            print(f"{servidor.nombre} | {servidor.ip}")

    def print_servidor_detail(self, nombre: str) -> None:
        servidor = self.get_servidor(nombre)
        print(f"Nombre: {servidor.nombre}")
        print(f"IP: {servidor.ip}")
        if servidor.mac:
            print(f"MAC: {servidor.mac}")
        print("Servicios:")
        for servicio in servidor.servicios.values():
            print(f"  - {servicio.nombre} | {servicio.protocolo} | {servicio.puerto}")

    def print_conexiones(self) -> None:
        for conexion in self.list_conexiones():
            print(
                f"{conexion.handler} | alumno={conexion.codigo_alumno} | "
                f"servidor={conexion.nombre_servidor} | servicio={conexion.nombre_servicio}"
            )


def prompt(text: str) -> str:
    return input(text).strip()


def cursos_menu(app: Lab4SDNApp) -> None:
    while True:
        print("\nCursos: [1] Listar [2] Mostrar detalle [3] Agregar alumno [4] Quitar alumno [0] Volver")
        option = prompt("> ")
        try:
            if option == "1":
                app.print_cursos()
            elif option == "2":
                app.print_curso_detail(prompt("Codigo del curso: "))
            elif option == "3":
                app.add_alumno_to_curso(prompt("Codigo del curso: "), prompt("Codigo del alumno: "))
                print("Alumno agregado.")
            elif option == "4":
                app.remove_alumno_from_curso(prompt("Codigo del curso: "), prompt("Codigo del alumno: "))
                print("Alumno eliminado.")
            elif option == "0":
                return
            else:
                print("Opcion invalida.")
        except Exception as exc:
            print(f"Error: {exc}")


def alumnos_menu(app: Lab4SDNApp) -> None:
    while True:
        print("\nAlumnos: [1] Listar [2] Mostrar detalle [0] Volver")
        option = prompt("> ")
        try:
            if option == "1":
                filtro = prompt("Filtro opcional (Enter para todos): ")
                app.print_alumnos(filtro or None)
            elif option == "2":
                app.print_alumno_detail(prompt("Codigo del alumno: "))
            elif option == "0":
                return
            else:
                print("Opcion invalida.")
        except Exception as exc:
            print(f"Error: {exc}")


def servidores_menu(app: Lab4SDNApp) -> None:
    while True:
        print("\nServidores: [1] Listar [2] Mostrar detalle [0] Volver")
        option = prompt("> ")
        try:
            if option == "1":
                app.print_servidores()
            elif option == "2":
                app.print_servidor_detail(prompt("Nombre del servidor: "))
            elif option == "0":
                return
            else:
                print("Opcion invalida.")
        except Exception as exc:
            print(f"Error: {exc}")


def conexiones_menu(app: Lab4SDNApp) -> None:
    while True:
        print("\nConexiones: [1] Crear [2] Listar [3] Borrar [0] Volver")
        option = prompt("> ")
        try:
            if option == "1":
                conexion = app.create_connection(
                    prompt("Codigo del alumno: "),
                    prompt("Nombre del servidor: "),
                    prompt("Nombre del servicio: "),
                )
                print(f"Conexion creada con handler {conexion.handler}")
            elif option == "2":
                app.print_conexiones()
            elif option == "3":
                warnings = app.delete_connection(prompt("Handler: "))
                print("Conexion eliminada.")
                for item in warnings:
                    print(item)
            elif option == "0":
                return
            else:
                print("Opcion invalida.")
        except Exception as exc:
            print(f"Error: {exc}")


def menu(app: Lab4SDNApp) -> None:
    while True:
        print("\nMenu principal")
        print("[1] Importar")
        print("[2] Exportar")
        print("[3] Cursos")
        print("[4] Alumnos")
        print("[5] Servidores")
        print("[6] Politicas")
        print("[7] Conexiones")
        print("[0] Salir")
        option = prompt("> ")

        try:
            if option == "1":
                app.import_from_yaml(prompt("Ruta del archivo YAML: "))
                print("Importacion completada.")
            elif option == "2":
                app.export_to_yaml(prompt("Ruta de salida YAML: "))
                print("Exportacion completada.")
            elif option == "3":
                cursos_menu(app)
            elif option == "4":
                alumnos_menu(app)
            elif option == "5":
                servidores_menu(app)
            elif option == "6":
                print("Politicas: la logica se deriva de cursos y servicios permitidos.")
            elif option == "7":
                conexiones_menu(app)
            elif option == "0":
                return
            else:
                print("Opcion invalida.")
        except Exception as exc:
            print(f"Error: {exc}")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="TEL354 Lab 4 SDN CLI")
    parser.add_argument("--data", help="YAML file to preload at startup")
    parser.add_argument("--controller", default="http://127.0.0.1:8080", help="Floodlight base URL")
    args = parser.parse_args(list(argv) if argv is not None else None)

    app = Lab4SDNApp(controller=FloodlightClient(base_url=args.controller))
    if args.data:
        app.import_from_yaml(args.data)
        print(f"Loaded data from {args.data}")
    menu(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
