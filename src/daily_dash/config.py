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
        "tide_station_id": "9414290",
        "tide_station_name": "San Francisco (Golden Gate / Ocean Beach)",
        "google_calendars": [
            "mjalexja@gmail.com",
            "amarchev91@gmail.com",
            "marchevskiy@google.com",
            "bsluuk01fgq0b4pnilh7cokh02i1s7o0@import.calendar.google.com",
            "avv0m5q0qdejhoq2f3fpqq6epqoei0k8@import.calendar.google.com",
        ],
        "tasks_google_doc_id": "1Eq83UhagQoYmPsa1FgzG-nOhEATU6Hld-0CTZIH3BaY",
        "automations_google_doc_id": "1K35_qv3yVfncwUodoX-FFTxcB01fscgHzE_cm6MFMFs",
        "home_maint_sheet_id": "1ZmdplUP0z-RmeyIEXsHgqml59pNDNEMz6LgHFWcVpnA",
    },
    "refresh_intervals": {
        "system_metrics_sec": 2.0,
        "weather_sec": 900.0,
        "calendar_sec": 300.0,
        "smart_home_sec": 15.0,
    },
    "automations": [
        {
            "name": "Weekly Family & Schedule Planner",
            "script_id": "1muxR2N_g2W1Zj…",
            "status": "HEALTHY",
            "runtime": "V8",
            "timezone": "America/Los_Angeles",
            "last_checked": "2026-11-25 08:18 PST",
            "last_updated": "2026-11-22",
            "details": "Verified: Weekly Family Plan Draft (Nov 23 - Nov 27, 2026)",
        },
        {
            "name": "Eddie's List Monthly Calendar Sync",
            "script_id": "1tZofJdyt24HY_…",
            "status": "HEALTHY",
            "runtime": "V8",
            "timezone": "America/Los_Angeles",
            "last_checked": "2026-11-25 08:18 PST",
            "last_updated": "2026-11-21",
            "details": "Synced monthly SF comedy/events to Eddie's List calendar",
        },
        {
            "name": "Reddit Digest",
            "script_id": "1Kf1xhVXqjSdJ8…",
            "status": "HEALTHY",
            "runtime": "V8",
            "timezone": "America/Los_Angeles",
            "last_checked": "2026-11-25 08:18 PST",
            "last_updated": "2026-11-20",
            "details": "Daily digest email active (1 deployment)",
        },
        {
            "name": "Archive Labeled Emails",
            "script_id": "1nwtJEvVM4o_CG…",
            "status": "HEALTHY",
            "runtime": "V8",
            "timezone": "America/Mexico_City",
            "last_checked": "2026-11-25 08:18 PST",
            "last_updated": "2021-09-17",
            "details": "Auto-archive filter deployment active",
        },
    ],
    "smart_home_auth": {
        "google_sdm_project_id": "",
        "google_sdm_client_id": "",
        "google_sdm_client_secret": "",
        "google_sdm_refresh_token": "",
        "google_sdm_access_token": "",
        "ha_url": "",
        "ha_token": "",
    },
    "google_home_devices": [
        {
            "id": "sf-nest-thermostat",
            "name": "Nest Thermostat",
            "room": "Hallway / Main",
            "type": "thermostat",
            "hvac_mode": "Heating",
            "temp_f": 69,
            "target_f": 70,
            "downstairs_temp_f": 68,
            "humidity": 46,
            "state": "Heating • 69°F → 70°F • Downstairs 68°F • 46% RH",
            "online": True,
            "active": True,
        },
        {
            "id": "sf-kitchen-nest-hub",
            "name": "Kitchen Nest Speaker",
            "room": "Kitchen",
            "type": "speaker",
            "volume_pct": 45,
            "muted": False,
            "media": "KQED / Cast Ready",
            "state": "KQED / Cast Ready • Vol 45%",
            "online": True,
            "active": True,
        },
        {
            "id": "sf-living-nest-audio",
            "name": "Living Room Nest Speaker",
            "room": "Living Room",
            "type": "speaker",
            "volume_pct": 30,
            "muted": False,
            "media": "Cast Ready",
            "state": "Cast Ready • Vol 30%",
            "online": True,
            "active": True,
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
        {
            "id": "t-7",
            "title": "Camera-scope cast-iron/clay sewer lateral to street trap",
            "priority": "P3",
            "project": "Q4 CapEx",
            "due": "Nov-Jan",
            "done": False,
        },
    ],
    "emails": [
        {
            "sender": "Apps Script Monitor",
            "subject": "[HEALTHY] All 4 scripts (Family Planner, Eddie's List, Reddit, Archive) V8 OK",
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
            "time": "17:15 - 18:00",
            "title": "[MJ] Dinner (Takeout / Sheet-Pan Chicken)",
            "location": "Home",
            "status": "upcoming",
            "calendar": "Family",
        },
        {
            "time": "18:00 - 18:25",
            "title": "[Alex] Leo Bath Time",
            "location": "Home",
            "status": "upcoming",
            "calendar": "Family",
        },
        {
            "time": "19:00 - 20:00",
            "title": "[MJ] Leo Bed Time",
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


def merge_discovered_devices(
    existing_devices: list[dict[str, Any]],
    discovered_devices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge live-discovered LAN/SDM devices with existing config devices:
    - If real speakers (`type == 'speaker'`) were discovered on the LAN, replace any
      placeholder speakers (those without a matching LAN IP) so only your real speakers appear.
    - If real thermostats (`type == 'thermostat'`) were discovered via Nest SDM / Matter,
      replace placeholder thermostats; otherwise keep your Nest Thermostat at the top of the pane.
    - Keep non-speaker/non-thermostat devices (locks, sensors, etc.) after your thermostats & speakers.
    """
    disc_thermostats = [d for d in discovered_devices if d.get("type") == "thermostat"]
    disc_speakers = [d for d in discovered_devices if d.get("type") == "speaker"]

    existing_thermostats = [d for d in existing_devices if d.get("type") == "thermostat"]
    existing_speakers = [d for d in existing_devices if d.get("type") == "speaker"]
    existing_other = [d for d in existing_devices if d.get("type") not in ("thermostat", "speaker")]

    final_thermostats = disc_thermostats if disc_thermostats else existing_thermostats[:1]
    final_speakers = disc_speakers if disc_speakers else existing_speakers[:2]

    return (final_thermostats + final_speakers + existing_other)[:10]


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

        discovered = scan_network(subnet=subnet, auth_cfg=cfg.get("smart_home_auth"))
        if discovered.get("google_home_devices"):
            cfg["google_home_devices"] = merge_discovered_devices(
                cfg.get("google_home_devices", []),
                discovered["google_home_devices"],
            )

        if discovered.get("managed_hosts"):
            existing_ips = {h.get("ip") for h in discovered["managed_hosts"]}
            merged_hosts = list(discovered["managed_hosts"])
            for h in cfg.get("managed_hosts", []):
                if h.get("ip") not in existing_ips:
                    merged_hosts.append(h)
            cfg["managed_hosts"] = merged_hosts[:8]

    return save_config(cfg, target_path)
