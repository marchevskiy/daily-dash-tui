"""Local LAN & mDNS/Bonjour auto-discovery for Google Home/Cast, Matter, and managed hosts."""

from __future__ import annotations

import ipaddress
import platform
import re
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any


# Common ports used by Google Cast / Nest / Matter / SSH / macOS
PORT_SIGNATURES: list[tuple[int, str, str]] = [
    (8008, "speaker", "Google Cast / Nest Device (HTTP :8008)"),
    (8009, "speaker", "Google Cast / Nest Hub (TLS :8009)"),
    (8443, "speaker", "Google Home Local API (:8443)"),
    (5540, "thermostat", "Matter Smart Home Device (:5540)"),
    (22, "host", "SSH Managed Machine (:22)"),
    (548, "host", "macOS AFP / MacBook (:548)"),
    (5900, "host", "macOS Screen Sharing / VNC (:5900)"),
]

MDNS_SERVICES: list[tuple[str, str, str]] = [
    ("_googlecast._tcp", "speaker", "Google Cast / Nest"),
    ("_matter._tcp", "thermostat", "Matter Device"),
    ("_hap._tcp", "lock", "HomeKit / Smart Home Bridge"),
    ("_ssh._tcp", "host", "SSH Host"),
    ("_companion-link._tcp", "host", "Apple / MacBook"),
]


def get_local_ip_and_subnet() -> tuple[str, str]:
    """Determine the active local IPv4 address and /24 subnet."""
    local_ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass

    try:
        net = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        return local_ip, str(net)
    except Exception:
        return local_ip, "192.168.86.0/24"


def _probe_tcp_port(ip: str, port: int, timeout: float = 0.25) -> bool:
    """Return True if TCP connection to ip:port succeeds within timeout."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0
    except Exception:
        return False


def _fetch_google_cast_eureka_info(ip: str, timeout: float = 0.6) -> dict[str, Any] | None:
    """Query Google Cast / Nest local eureka_info endpoint on port 8008 if reachable."""
    import httpx

    for path in ("/setup/eureka_info?options=detail", "/setup/eureka_info"):
        url = f"http://{ip}:8008{path}"
        try:
            resp = httpx.get(url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("name"):
                    return data
        except Exception:
            continue
    return None


def discover_mdns_services(timeout_sec: float = 2.0) -> list[dict[str, Any]]:
    """Run mDNS/Bonjour discovery using macOS `dns-sd` or Linux `avahi-browse`."""
    discovered: list[dict[str, Any]] = []

    if shutil.which("avahi-browse"):
        try:
            proc = subprocess.run(
                ["avahi-browse", "-a", "-t", "-r", "-p"],
                capture_output=True,
                text=True,
                timeout=timeout_sec + 1.0,
            )
            for line in proc.stdout.splitlines():
                if not line.startswith("="):
                    continue
                parts = line.split(";")
                if len(parts) >= 9:
                    svc_name = parts[3]
                    svc_type = parts[4]
                    host = parts[6]
                    ip = parts[7]
                    port = parts[8]
                    discovered.append(
                        {
                            "name": svc_name,
                            "service": svc_type,
                            "hostname": host,
                            "ip": ip,
                            "port": port,
                            "source": "mDNS (avahi)",
                        }
                    )
        except Exception:
            pass

    elif shutil.which("dns-sd"):
        # On macOS, query _googlecast._tcp and _ssh._tcp with a short timeout
        for svc, dtype, label in MDNS_SERVICES[:3]:
            try:
                proc = subprocess.Popen(
                    ["dns-sd", "-B", svc, "local."],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    out, _ = proc.communicate(timeout=timeout_sec)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    out, _ = proc.communicate()

                for line in (out or "").splitlines():
                    if "Add" in line and svc in line:
                        instance = line.split(svc)[-1].strip().lstrip(".")
                        if instance:
                            discovered.append(
                                {
                                    "name": instance,
                                    "service": svc,
                                    "type": dtype,
                                    "label": label,
                                    "source": "Bonjour (dns-sd)",
                                }
                            )
            except Exception:
                continue

    return discovered


def parse_arp_neighbors() -> list[dict[str, str]]:
    """Inspect local ARP / neighbor cache (`ip neigh` or `arp -a`) for active LAN devices."""
    neighbors: list[dict[str, str]] = []
    seen_ips: set[str] = set()

    if shutil.which("ip"):
        try:
            proc = subprocess.run(
                ["ip", "neigh", "show"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            for line in proc.stdout.splitlines():
                parts = line.split()
                if not parts:
                    continue
                ip = parts[0]
                if ":" in ip or ip in seen_ips:
                    continue
                mac = ""
                if "lladdr" in parts:
                    idx = parts.index("lladdr")
                    if idx + 1 < len(parts):
                        mac = parts[idx + 1]
                state = parts[-1]
                if state in ("REACHABLE", "STALE", "DELAY", "PERMANENT"):
                    seen_ips.add(ip)
                    neighbors.append({"ip": ip, "mac": mac, "hostname": _resolve_hostname(ip)})
        except Exception:
            pass

    if shutil.which("arp"):
        try:
            proc = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            for line in proc.stdout.splitlines():
                m = re.search(r"(?P<host>\S+)\s+\((?P<ip>\d+\.\d+\.\d+\.\d+)\)\s+at\s+(?P<mac>[0-9a-fA-F:]+)", line)
                if m:
                    ip = m.group("ip")
                    if ip not in seen_ips:
                        seen_ips.add(ip)
                        host = m.group("host")
                        neighbors.append(
                            {
                                "ip": ip,
                                "mac": m.group("mac"),
                                "hostname": host if host != "?" else _resolve_hostname(ip),
                            }
                        )
        except Exception:
            pass

    return neighbors


def _resolve_hostname(ip: str) -> str:
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except Exception:
        return ip


def scan_network(
    subnet: str | None = None,
    timeout: float = 0.25,
    max_hosts: int = 64,
) -> dict[str, Any]:
    """Scan the local network (mDNS + ARP cache + concurrent TCP port probes)
    and return discovered `google_home_devices` and `managed_hosts`.
    """
    local_ip, detected_subnet = get_local_ip_and_subnet()
    target_subnet = subnet or detected_subnet

    mdns_items = discover_mdns_services(timeout_sec=1.2)
    arp_items = parse_arp_neighbors()

    # Build candidate IP list starting with ARP neighbors + gateway/common offsets
    candidate_ips: list[str] = [n["ip"] for n in arp_items]
    try:
        net = ipaddress.IPv4Network(target_subnet, strict=False)
        for host_ip in list(net.hosts())[:max_hosts]:
            s_ip = str(host_ip)
            if s_ip not in candidate_ips and s_ip != local_ip:
                candidate_ips.append(s_ip)
    except Exception:
        pass

    candidate_ips = candidate_ips[:max_hosts]

    google_home_devices: list[dict[str, Any]] = []
    managed_hosts: list[dict[str, Any]] = [
        {
            "hostname": socket.gethostname(),
            "role": f"Local Workstation ({platform.system()} {platform.machine()})",
            "ip": local_ip,
            "cpu_model": platform.processor() or platform.machine(),
            "battery_pct": 100,
            "power_plugged": True,
            "online": True,
        }
    ]

    arp_by_ip = {n["ip"]: n for n in arp_items}

    def _inspect_ip(ip: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        found_gh: list[dict[str, Any]] = []
        found_hosts: list[dict[str, Any]] = []
        host_label = arp_by_ip.get(ip, {}).get("hostname") or ip

        # Check Google Cast / Google Home ports
        is_cast = _probe_tcp_port(ip, 8008, timeout) or _probe_tcp_port(ip, 8009, timeout) or _probe_tcp_port(ip, 8443, timeout)
        if is_cast:
            eureka = _fetch_google_cast_eureka_info(ip, timeout=0.5)
            dev_name = (eureka or {}).get("name") or f"Google Home ({host_label})"
            room = (eureka or {}).get("room_name") or "LAN"
            model = (eureka or {}).get("detail", {}).get("model_name") or "Google Cast / Nest"
            found_gh.append(
                {
                    "id": f"gh-{ip.replace('.', '-')}",
                    "name": dev_name,
                    "room": room,
                    "type": "speaker",
                    "state": f"Online • {model} ({ip})",
                    "ip": ip,
                    "online": True,
                    "active": True,
                }
            )

        # Check Matter port (5540)
        if _probe_tcp_port(ip, 5540, timeout):
            found_gh.append(
                {
                    "id": f"matter-{ip.replace('.', '-')}",
                    "name": f"Matter Device ({host_label})",
                    "room": "Smart Home LAN",
                    "type": "thermostat",
                    "state": f"Connected • Matter (:5540 @ {ip})",
                    "ip": ip,
                    "online": True,
                    "active": True,
                }
            )

        # Check SSH / macOS ports
        is_ssh = _probe_tcp_port(ip, 22, timeout)
        is_mac = _probe_tcp_port(ip, 548, timeout) or _probe_tcp_port(ip, 5900, timeout)
        if is_ssh or is_mac or ip in arp_by_ip:
            role = "macOS / Apple Host" if is_mac else ("SSH Server / Node" if is_ssh else "LAN Neighbor")
            found_hosts.append(
                {
                    "hostname": host_label,
                    "role": f"{role} ({ip})",
                    "ip": ip,
                    "cpu_pct": 0.0,
                    "mem_pct": 0.0,
                    "disk_pct": 0.0,
                    "online": True,
                }
            )

        return found_gh, found_hosts

    with ThreadPoolExecutor(max_workers=24) as pool:
        for gh_list, host_list in pool.map(_inspect_ip, candidate_ips):
            google_home_devices.extend(gh_list)
            managed_hosts.extend(host_list)

    # Also incorporate mDNS discoveries not caught by IP scan
    seen_names = {d["name"] for d in google_home_devices}
    for item in mdns_items:
        name = item.get("name", "")
        if name and name not in seen_names and item.get("type") != "host":
            seen_names.add(name)
            google_home_devices.append(
                {
                    "id": f"mdns-{len(google_home_devices)+1}",
                    "name": name,
                    "room": "mDNS / Bonjour",
                    "type": item.get("type", "speaker"),
                    "state": f"Online • {item.get('source', 'mDNS')}",
                    "online": True,
                    "active": True,
                }
            )

    return {
        "local_ip": local_ip,
        "subnet": target_subnet,
        "arp_neighbors": arp_items,
        "mdns_services": mdns_items,
        "google_home_devices": google_home_devices,
        "managed_hosts": managed_hosts,
    }
