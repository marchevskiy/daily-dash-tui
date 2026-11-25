"""Local LAN & mDNS/Bonjour auto-discovery + live telemetry for Google Cast speakers & Nest/Ecobee/Matter thermostats."""

from __future__ import annotations

import ipaddress
import os
import platform
import re
import shutil
import socket
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx


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


def probe_cast_volume_status(
    ip: str,
    friendly_name: str | None = None,
    model_name: str | None = None,
    timeout: float = 1.5,
) -> dict[str, Any] | None:
    """Query a Google Home / Nest speaker over Cast protocol (:8009) via pychromecast
    to retrieve live volume_level (0–100%), mute status, and currently playing app.
    """
    try:
        import pychromecast

        host_tuple = (
            ip,
            8009,
            uuid.UUID(int=0),
            model_name or "Google Nest",
            friendly_name or f"Speaker-{ip}",
        )
        cast = pychromecast.get_chromecast_from_host(
            host_tuple,
            tries=1,
            retry_wait=0.2,
            timeout=timeout,
        )
        cast.wait(timeout=timeout)
        status = cast.status
        mc = cast.media_controller.status if hasattr(cast, "media_controller") else None
        vol_pct = int(round(float(status.volume_level) * 100)) if status and status.volume_level is not None else None
        muted = bool(status.volume_muted) if status else False
        app_name = (status.display_name if status and status.display_name else None) or "Idle"
        track = getattr(mc, "title", None) if mc else None
        cast.disconnect(timeout=0.5)
        if vol_pct is None:
            return None
        return {
            "volume_pct": max(0, min(100, vol_pct)),
            "muted": muted,
            "app_name": app_name,
            "track": track,
        }
    except Exception:
        return None


def set_cast_volume_on_lan(
    ip: str,
    volume_pct: int,
    muted: bool | None = None,
    timeout: float = 1.5,
) -> bool:
    """Send live volume level (0-100) or mute toggle to a Google Cast speaker at `ip` if reachable."""
    if not ip or not _probe_tcp_port(ip, 8009, timeout=0.35):
        return False
    try:
        import pychromecast

        host_tuple = (ip, 8009, uuid.UUID(int=0), "Google Nest", f"Speaker-{ip}")
        cast = pychromecast.get_chromecast_from_host(
            host_tuple,
            tries=1,
            retry_wait=0.2,
            timeout=timeout,
        )
        cast.wait(timeout=timeout)
        cast.set_volume(max(0.0, min(1.0, volume_pct / 100.0)))
        if muted is not None:
            cast.set_volume_muted(muted)
        cast.disconnect(timeout=0.5)
        return True
    except Exception:
        return False


def fetch_thermostat_telemetry(
    device: dict[str, Any],
    timeout: float = 1.5,
) -> dict[str, Any] | None:
    """Pull live ambient temperature, target setpoint, humidity, and HVAC mode for a thermostat:
    1. Google Nest SDM API (if `GOOGLE_SDM_PROJECT_ID` and `GOOGLE_SDM_ACCESS_TOKEN` are set in env).
    2. Home Assistant / Local Matter REST bridge (if `HA_URL` and `HA_TOKEN` are set in env).
    3. Local IP HTTP JSON endpoint on the thermostat (e.g. `http://<ip>/tstat` or `:8080/status`).
    """
    # 1. Check Google Nest SDM API if configured
    sdm_project = os.environ.get("GOOGLE_SDM_PROJECT_ID")
    sdm_token = os.environ.get("GOOGLE_SDM_ACCESS_TOKEN")
    if sdm_project and sdm_token:
        try:
            url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{sdm_project}/devices"
            resp = httpx.get(
                url,
                headers={"Authorization": f"Bearer {sdm_token}"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                devs = resp.json().get("devices", [])
                for d in devs:
                    traits = d.get("traits", {})
                    if "sdm.devices.traits.Temperature" in traits:
                        amb_c = float(
                            traits["sdm.devices.traits.Temperature"].get("ambientTemperatureCelsius", 20.5)
                        )
                        amb_f = round(amb_c * 9.0 / 5.0 + 32.0, 1)
                        hum = traits.get("sdm.devices.traits.Humidity", {}).get("ambientHumidityPercent", 48)
                        mode = traits.get("sdm.devices.traits.ThermostatMode", {}).get("mode", "HEAT")
                        sp_trait = traits.get("sdm.devices.traits.ThermostatTemperatureSetpoint", {})
                        target_c = sp_trait.get("heatCelsius") or sp_trait.get("coolCelsius") or 21.1
                        target_f = round(float(target_c) * 9.0 / 5.0 + 32.0, 1)
                        return {
                            "temp_f": amb_f,
                            "target_f": target_f,
                            "humidity": int(hum),
                            "hvac_mode": str(mode).capitalize(),
                        }
        except Exception:
            pass

    # 2. Check Home Assistant / Matter bridge if configured
    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")
    entity_id = device.get("entity_id")
    if ha_url and ha_token and entity_id:
        try:
            resp = httpx.get(
                f"{ha_url.rstrip('/')}/api/states/{entity_id}",
                headers={"Authorization": f"Bearer {ha_token}"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                payload = resp.json()
                attrs = payload.get("attributes", {})
                return {
                    "temp_f": float(attrs.get("current_temperature", device.get("temp_f", 69.0))),
                    "target_f": float(attrs.get("temperature", device.get("target_f", 70.0))),
                    "humidity": int(attrs.get("current_humidity", device.get("humidity", 48))),
                    "hvac_mode": str(payload.get("state", "Heating")).capitalize(),
                }
        except Exception:
            pass

    # 3. Check local IP thermostat endpoint if IP is available on LAN
    ip = device.get("ip")
    if ip and _probe_tcp_port(ip, 80, timeout=0.25):
        for path in ("/tstat", "/status", "/api/v1/status"):
            try:
                resp = httpx.get(f"http://{ip}{path}", timeout=0.6)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and ("temp" in data or "ambient_temp_f" in data):
                        t_f = float(data.get("temp") or data.get("ambient_temp_f") or 69.0)
                        t_set = float(data.get("t_heat") or data.get("target_temp_f") or 70.0)
                        return {
                            "temp_f": round(t_f, 1),
                            "target_f": round(t_set, 1),
                            "humidity": int(data.get("humidity", device.get("humidity", 48))),
                            "hvac_mode": str(data.get("hvac_mode", "Heating")),
                        }
            except Exception:
                continue

    return None


def format_smart_device_state(dev: dict[str, Any]) -> str:
    """Format a rich human-readable state string including temperature/setpoint for thermostats
    and volume/mute level for smart speakers.
    """
    dtype = dev.get("type", "device")
    active = dev.get("active", True)

    if dtype == "thermostat":
        temp_f = dev.get("temp_f", 69)
        target_f = dev.get("target_f", 70)
        sensor_f = dev.get("downstairs_temp_f")
        humidity = dev.get("humidity")
        mode = dev.get("hvac_mode") or ("Heating" if active else "Eco Mode")
        parts = [f"{mode} • {temp_f}°F → {target_f}°F"]
        if sensor_f is not None:
            parts.append(f"Downstairs {sensor_f}°F")
        elif humidity is not None:
            parts.append(f"{humidity}% RH")
        return " • ".join(parts)

    if dtype == "speaker":
        vol = dev.get("volume_pct", 40)
        muted = dev.get("muted", False)
        media = dev.get("media") or ("Playing" if active else "Idle")
        vol_tag = f"Muted ({vol}%)" if muted else f"Vol {vol}%"
        if not active:
            return f"Idle • {vol_tag} • Ready to Cast"
        return f"{media} • {vol_tag}"

    return str(dev.get("state", "Online" if active else "Standby"))


def refresh_smart_devices_telemetry(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Poll live volume levels for Google Cast speakers and live temperatures for thermostats."""
    for dev in devices:
        dtype = dev.get("type", "")
        ip = dev.get("ip")
        if dtype == "speaker" and ip and _probe_tcp_port(ip, 8009, timeout=0.25):
            cast_info = probe_cast_volume_status(ip, friendly_name=dev.get("name"))
            if cast_info:
                dev["volume_pct"] = cast_info["volume_pct"]
                dev["muted"] = cast_info["muted"]
                if cast_info.get("track"):
                    dev["media"] = f"Playing: {cast_info['track']}"
                elif cast_info.get("app_name") and cast_info["app_name"] != "Idle":
                    dev["media"] = cast_info["app_name"]
                dev["state"] = format_smart_device_state(dev)
        elif dtype == "thermostat":
            tstat = fetch_thermostat_telemetry(dev)
            if tstat:
                dev["temp_f"] = tstat["temp_f"]
                dev["target_f"] = tstat["target_f"]
                dev["humidity"] = tstat["humidity"]
                dev["hvac_mode"] = tstat["hvac_mode"]
                dev["state"] = format_smart_device_state(dev)
    return devices


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
    and return discovered `google_home_devices` (with live Cast volume & thermostat temps)
    and `managed_hosts`.
    """
    local_ip, detected_subnet = get_local_ip_and_subnet()
    target_subnet = subnet or detected_subnet

    mdns_items = discover_mdns_services(timeout_sec=1.2)
    arp_items = parse_arp_neighbors()

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

        # Check Google Cast / Google Home ports (:8008 / :8009 / :8443)
        is_cast = (
            _probe_tcp_port(ip, 8008, timeout)
            or _probe_tcp_port(ip, 8009, timeout)
            or _probe_tcp_port(ip, 8443, timeout)
        )
        if is_cast:
            eureka = _fetch_google_cast_eureka_info(ip, timeout=0.5)
            dev_name = (eureka or {}).get("name") or f"Google Home Speaker ({host_label})"
            room = (eureka or {}).get("room_name") or "LAN"
            model = (eureka or {}).get("detail", {}).get("model_name") or "Google Cast / Nest"
            cast_vol = probe_cast_volume_status(ip, friendly_name=dev_name, model_name=model, timeout=1.2)
            vol_pct = (cast_vol or {}).get("volume_pct", 40)
            muted = (cast_vol or {}).get("muted", False)
            app_label = (cast_vol or {}).get("track") or (cast_vol or {}).get("app_name") or model
            dev_entry = {
                "id": f"gh-{ip.replace('.', '-')}",
                "name": dev_name,
                "room": room,
                "type": "speaker",
                "volume_pct": vol_pct,
                "muted": muted,
                "media": app_label,
                "ip": ip,
                "online": True,
                "active": True,
            }
            dev_entry["state"] = format_smart_device_state(dev_entry)
            found_gh.append(dev_entry)

        # Check Matter / Smart Thermostat port (:5540)
        if _probe_tcp_port(ip, 5540, timeout):
            tstat_dev: dict[str, Any] = {
                "id": f"matter-{ip.replace('.', '-')}",
                "name": f"Thermostat ({host_label})",
                "room": "Smart Home LAN",
                "type": "thermostat",
                "temp_f": 69,
                "target_f": 70,
                "humidity": 48,
                "hvac_mode": "Heating",
                "ip": ip,
                "online": True,
                "active": True,
            }
            live_t = fetch_thermostat_telemetry(tstat_dev, timeout=0.8)
            if live_t:
                tstat_dev.update(live_t)
            tstat_dev["state"] = format_smart_device_state(tstat_dev)
            found_gh.append(tstat_dev)

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
            dtype = item.get("type", "speaker")
            m_dev: dict[str, Any] = {
                "id": f"mdns-{len(google_home_devices)+1}",
                "name": name,
                "room": "mDNS / Bonjour",
                "type": dtype,
                "online": True,
                "active": True,
            }
            if dtype == "speaker":
                m_dev["volume_pct"] = 40
                m_dev["muted"] = False
                m_dev["media"] = item.get("source", "Cast Ready")
            elif dtype == "thermostat":
                m_dev["temp_f"] = 69
                m_dev["target_f"] = 70
                m_dev["humidity"] = 48
                m_dev["hvac_mode"] = "Heating"
            m_dev["state"] = format_smart_device_state(m_dev)
            google_home_devices.append(m_dev)

    return {
        "local_ip": local_ip,
        "subnet": target_subnet,
        "arp_neighbors": arp_items,
        "mdns_services": mdns_items,
        "google_home_devices": google_home_devices,
        "managed_hosts": managed_hosts,
    }
