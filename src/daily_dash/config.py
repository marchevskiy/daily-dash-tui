"""Configuration loader and personalized settings for DailyDash TUI."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "profile": {
        "name": "Alex",
        "primary_host": "Alex-MacBook-Pro.local",
        "location": "San Francisco, CA",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "temperature_unit": "fahrenheit",
        "google_calendars": [
            "mjalexja@gmail.com",
            "amarchev91@gmail.com",
            "marchevskiy@google.com",
            "bsluuk01fgq0b4pnilh7cokh02i1s7o0@import.calendar.google.com",
            "avv0m5q0qdejhoq2f3fpqq6epqoei0k8@import.calendar.google.com",
        ],
        "tasks_google_doc_id": "1Eq83UhagQoYmPsa1FgzG-nOhEATU6Hld-0CTZIH3BaY",
        "home_maint_sheet_id": "1ZmdplUP0z-RmeyIEXsHgqml59pNDNEMz6LgHFWcVpnA",
    },
    "refresh_intervals": {
        "system_metrics_sec": 2.0,
        "weather_sec": 900.0,
        "calendar_sec": 300.0,
        "smart_home_sec": 15.0,
    },
    "google_home_devices": [
        {
            "id": "sf-thermostat-dual",
            "name": "Upstairs & Downstairs Nest Thermostat",
            "room": "Main & Ground",
            "type": "thermostat",
            "state": "Heating • 69°F (Downstairs Sensor 68°F)",
            "online": True,
            "active": True,
            "temp_f": 69,
            "target_f": 70,
        },
        {
            "id": "sf-nest-protect",
            "name": "Nest Protect Smoke/CO & Garage Heat",
            "room": "All Levels",
            "type": "air",
            "state": "All Clear • Garage Rate-of-Rise OK",
            "online": True,
            "active": True,
        },
        {
            "id": "sf-front-deadbolt",
            "name": "Front Tunnel & Yard Smart Deadbolts",
            "room": "Entry & Patio",
            "type": "lock",
            "state": "Locked • Battery 94% (PTFE Lubed)",
            "online": True,
            "active": True,
        },
        {
            "id": "sf-garage-opener",
            "name": "Wi-Fi Garage Door Opener & Lintel Cam",
            "room": "Garage",
            "type": "lock",
            "state": "Closed • Floodlight Cam Active",
            "online": True,
            "active": True,
        },
        {
            "id": "sf-leak-sensors",
            "name": "Wi-Fi Water Leak Sensors (5x Zones)",
            "room": "Mudroom/Utility",
            "type": "air",
            "state": "Dry • 48% Ground Floor Humidity",
            "online": True,
            "active": True,
        },
        {
            "id": "sf-warm-leds",
            "name": "2700K Warm White LEDs & Lutron Shades",
            "room": "Living / Office",
            "type": "light",
            "state": "On • 85% Warm White (90+ CRI)",
            "online": True,
            "active": True,
            "brightness": 85,
        },
    ],
    "managed_hosts": [
        {
            "hostname": "Alex-MacBook-Pro.local",
            "role": "Primary Workstation (SF / SVL / WFH)",
            "ip": "192.168.86.24",
            "cpu_model": "Apple Silicon M-Series",
            "battery_pct": 92,
            "power_plugged": True,
        },
        {
            "hostname": "nest-wifi-pro-gateway.local",
            "role": "SF Rowhouse Mesh Router & Matter Hub",
            "ip": "192.168.86.1",
            "cpu_pct": 11.4,
            "mem_pct": 42.0,
            "disk_pct": 18.0,
            "online": True,
        },
        {
            "hostname": "poe-nvr-cameras.local",
            "role": "3-Cam SF Rowhouse Security (Tunnel/Garage/Yard)",
            "ip": "192.168.86.15",
            "cpu_pct": 18.5,
            "mem_pct": 51.2,
            "disk_pct": 64.0,
            "online": True,
        },
    ],
    "tasks": [
        {
            "id": "t-1",
            "title": "Clear leaves from flat roof scuppers & patio drains (Nov–Mar)",
            "priority": "P0",
            "project": "SF Home",
            "due": "This Week",
            "done": False,
        },
        {
            "id": "t-2",
            "title": "Check/replace forced-air furnace filter (MERV 8-11 / MERV 13)",
            "priority": "P1",
            "project": "SF Home",
            "due": "Nov Maint",
            "done": False,
        },
        {
            "id": "t-3",
            "title": "Lubricate garage door torsion springs & rollers (white lithium)",
            "priority": "P1",
            "project": "SF Home",
            "due": "This Week",
            "done": False,
        },
        {
            "id": "t-4",
            "title": "Groceries: Milk, eggs, butter, bananas, berries, frozen backup",
            "priority": "P2",
            "project": "Shopping",
            "due": "Weekly",
            "done": False,
        },
        {
            "id": "t-5",
            "title": "Supplies: Leo (formula/diapers/wipes) & Pets (Kosmo Carprofen/Greenies, June litter)",
            "priority": "P2",
            "project": "Family",
            "due": "Weekly",
            "done": False,
        },
        {
            "id": "t-6",
            "title": "Seal stucco cracks around parapet walls & inspect skylight curb flashing",
            "priority": "P2",
            "project": "Q4 CapEx",
            "due": "Nov-Dec",
            "done": False,
        },
    ],
    "emails": [
        {
            "sender": "Apps Script Monitor",
            "subject": "[HEALTHY] Weekly Family Planner & Eddie's List Sync deployed (V8)",
            "time": "08:18 PST",
            "unread": True,
            "tag": "Automation",
        },
        {
            "sender": "Villa de Kapuso YMCA",
            "subject": "Reminder: Daycare Full Closure Thu Nov 26 – Fri Nov 27 (Thanksgiving)",
            "time": "Today",
            "unread": True,
            "tag": "Family",
        },
        {
            "sender": "SF Botanical Garden",
            "subject": "Tickets Ready: Lightscape at Gardens of Golden Gate Park (5:00 PM)",
            "time": "Today",
            "unread": True,
            "tag": "Events",
        },
        {
            "sender": "Reddit Digest Script",
            "subject": "Daily Automated Digest delivered from Apps Script (1Kf1xh...)",
            "time": "07:00 PST",
            "unread": False,
            "tag": "Digest",
        },
    ],
    "calendar_events": [
        {
            "time": "07:00 - 07:30",
            "title": "[Alex] Wake up with Leo",
            "location": "SF Rowhouse",
            "status": "completed",
            "calendar": "Family",
        },
        {
            "time": "08:00 - 08:30",
            "title": "[MJ] Morning Kosmo Walk (after 7a call)",
            "location": "Neighborhood",
            "status": "completed",
            "calendar": "Family",
        },
        {
            "time": "08:30 - 08:50",
            "title": "[MJ] Leo Daycare Drop-off",
            "location": "Villa de Kapuso",
            "status": "completed",
            "calendar": "Family",
        },
        {
            "time": "09:00 - 13:00",
            "title": "Daly City Farmers Market (Pre-Thanksgiving)",
            "location": "Serramonte Ctr",
            "status": "up_next",
            "calendar": "Family",
        },
        {
            "time": "15:30 - 16:00",
            "title": "[MJ] Afternoon Kosmo Walk (before 4:54p sunset)",
            "location": "Before Dark",
            "status": "upcoming",
            "calendar": "Family",
        },
        {
            "time": "16:30 - 16:50",
            "title": "[MJ] Leo Daycare Pick-up (<8h)",
            "location": "Villa de Kapuso",
            "status": "upcoming",
            "calendar": "Family",
        },
        {
            "time": "17:00 - 18:30",
            "title": "Lightscape at Gardens of Golden Gate Park",
            "location": "GGP Botanical",
            "status": "upcoming",
            "calendar": "Family",
        },
        {
            "time": "18:00 - 18:25",
            "title": "[Alex] Leo Bath Time & [MJ] Bed Time (19:00)",
            "location": "Home",
            "status": "upcoming",
            "calendar": "Family",
        },
    ],
    "habits": [
        {"name": "Walk Kosmo before 4:54 PM SF Sunset", "streak": 18, "done_today": True},
        {"name": "Leo Daycare Pick-up under 8hr window", "streak": 14, "done_today": True},
        {"name": "Ground Floor Humidity 40-55% & Scupper Check", "streak": 9, "done_today": False},
        {"name": "Leave Front-Load Washer Door Ajar", "streak": 27, "done_today": True},
    ],
    "world_clocks": [
        {"label": "SF / Sunnyvale", "tz": "America/Los_Angeles"},
        {"label": "Chicago (Bulls/Hawks)", "tz": "America/Chicago"},
        {"label": "New York / EST", "tz": "America/New_York"},
        {"label": "London (Arsenal FC)", "tz": "Europe/London"},
    ],
}


def get_default_config_path() -> Path:
    """Return standard XDG / home config file path."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "daily-dash" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load user YAML configuration merged over DEFAULT_CONFIG."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    path = Path(config_path) if config_path else get_default_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                user_cfg = yaml.safe_load(fh) or {}
            for key, value in user_cfg.items():
                if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                    cfg[key].update(value)
                else:
                    cfg[key] = value
        except Exception:
            pass
    return cfg


def save_config(cfg: dict[str, Any], target_path: str | Path | None = None) -> Path:
    """Save a configuration dictionary to YAML on disk."""
    path = Path(target_path) if target_path else get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)
    return path


def write_sample_config(
    target_path: str | Path,
    sync_google: bool = True,
    scan_lan: bool = False,
    subnet: str | None = None,
) -> Path:
    """Write a personalized config.yaml to disk, optionally pulling live Google Workspace
    data and scanning the local network for Google Home / LAN hosts.
    """
    cfg = copy.deepcopy(DEFAULT_CONFIG)

    if sync_google:
        from daily_dash.google_sync import sync_config_with_google

        sync_config_with_google(cfg)

    if scan_lan:
        from daily_dash.discovery import scan_network

        discovered = scan_network(subnet=subnet)
        if discovered.get("google_home_devices"):
            # Prepend live-discovered LAN devices ahead of configured home devices
            existing_names = {d["name"] for d in discovered["google_home_devices"]}
            merged_gh = list(discovered["google_home_devices"])
            for item in cfg.get("google_home_devices", []):
                if item["name"] not in existing_names:
                    merged_gh.append(item)
            cfg["google_home_devices"] = merged_gh[:8]

        if discovered.get("managed_hosts"):
            existing_ips = {h.get("ip") for h in discovered["managed_hosts"]}
            merged_hosts = list(discovered["managed_hosts"])
            for h in cfg.get("managed_hosts", []):
                if h.get("ip") not in existing_ips:
                    merged_hosts.append(h)
            cfg["managed_hosts"] = merged_hosts[:6]

    return save_config(cfg, target_path)
