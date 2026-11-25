"""Configuration loader and default settings for DailyDash TUI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "profile": {
        "name": "Alex",
        "primary_host": "MacBook-Pro-M3.local",
        "location": "San Francisco, CA",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "temperature_unit": "fahrenheit",
    },
    "refresh_intervals": {
        "system_metrics_sec": 2.0,
        "weather_sec": 900.0,
        "calendar_sec": 300.0,
        "smart_home_sec": 15.0,
    },
    "google_home_devices": [
        {
            "id": "gh-living-thermostat",
            "name": "Living Room Nest",
            "room": "Living Room",
            "type": "thermostat",
            "state": "Heating • 70°F (Target 72°F)",
            "online": True,
            "active": True,
            "temp_f": 70,
            "target_f": 72,
        },
        {
            "id": "gh-office-lights",
            "name": "Office Desk & Bias Lights",
            "room": "Home Office",
            "type": "light",
            "state": "On • 85% Warm White",
            "online": True,
            "active": True,
            "brightness": 85,
        },
        {
            "id": "gh-kitchen-hub",
            "name": "Kitchen Nest Hub Max",
            "room": "Kitchen",
            "type": "speaker",
            "state": "Playing • Lo-Fi Beats (40%)",
            "online": True,
            "active": True,
        },
        {
            "id": "gh-front-lock",
            "name": "Front Door Nest × Yale",
            "room": "Entryway",
            "type": "lock",
            "state": "Locked • Battery 92%",
            "online": True,
            "active": True,
        },
        {
            "id": "gh-bedroom-purifier",
            "name": "Bedroom Air Purifier",
            "room": "Master Bedroom",
            "type": "air",
            "state": "Auto • AQI 14 (Good)",
            "online": True,
            "active": True,
        },
        {
            "id": "gh-patio-lights",
            "name": "Patio String Lights",
            "room": "Backyard",
            "type": "light",
            "state": "Off • Scheduled 18:30",
            "online": True,
            "active": False,
        },
    ],
    "managed_hosts": [
        {
            "hostname": "MacBook-Pro-M3.local",
            "role": "Primary Workstation (macOS 15.2)",
            "ip": "192.168.86.24",
            "cpu_model": "Apple M3 Max (16-core)",
            "battery_pct": 88,
            "power_plugged": True,
        },
        {
            "hostname": "homelab-nas.local",
            "role": "Home Media & Backup Server",
            "ip": "192.168.86.10",
            "cpu_model": "AMD Ryzen 7 5800U",
            "cpu_pct": 14.2,
            "mem_pct": 48.5,
            "disk_pct": 62.1,
            "online": True,
        },
        {
            "hostname": "pi-pihole.local",
            "role": "DNS Sinkhole & Matter Bridge",
            "ip": "192.168.86.2",
            "cpu_model": "Raspberry Pi 5 (8GB)",
            "cpu_pct": 6.8,
            "mem_pct": 29.0,
            "disk_pct": 21.4,
            "online": True,
        },
    ],
    "tasks": [
        {
            "id": "t-1",
            "title": "Review Q4 architecture RFC & leave feedback",
            "priority": "P0",
            "project": "Work",
            "due": "Today 14:00",
            "done": False,
        },
        {
            "id": "t-2",
            "title": "Ship daily-dash-tui v0.1.0 to GitHub",
            "priority": "P1",
            "project": "Personal",
            "due": "Today 17:00",
            "done": False,
        },
        {
            "id": "t-3",
            "title": "Replace HVAC air filter & test Nest schedule",
            "priority": "P2",
            "project": "Home",
            "due": "Tomorrow",
            "done": False,
        },
        {
            "id": "t-4",
            "title": "Book dentist appointment & order coffee beans",
            "priority": "P2",
            "project": "Errands",
            "due": "Fri",
            "done": False,
        },
        {
            "id": "t-5",
            "title": "Update MacBook Homebrew packages & dotfiles backup",
            "priority": "P3",
            "project": "Ops",
            "due": "Done",
            "done": True,
        },
    ],
    "emails": [
        {
            "sender": "Sarah Chen (Eng Lead)",
            "subject": "[Action Required] Production rollout sign-off for v2.4",
            "time": "10m ago",
            "unread": True,
            "tag": "Work",
        },
        {
            "sender": "GitHub Notifications",
            "subject": "[marchevskiy/daily-dash-tui] CI pipeline passed on main",
            "time": "38m ago",
            "unread": True,
            "tag": "GitHub",
        },
        {
            "sender": "Google Home Security",
            "subject": "Weekly Home Report: 0 alerts, Nest energy savings +12%",
            "time": "2h ago",
            "unread": True,
            "tag": "Home",
        },
        {
            "sender": "Stripe Billing",
            "subject": "Invoice #4829-01 paid for Cloud Infrastructure ($24.00)",
            "time": "4h ago",
            "unread": False,
            "tag": "Finance",
        },
        {
            "sender": "Alex Rivera",
            "subject": "Re: Dinner plans this Friday — 7pm at Nopa?",
            "time": "Yesterday",
            "unread": False,
            "tag": "Personal",
        },
    ],
    "calendar_events": [
        {
            "time": "09:30 - 10:00",
            "title": "Morning Standup & Triage",
            "location": "Google Meet",
            "status": "completed",
            "calendar": "Work",
        },
        {
            "time": "11:00 - 11:45",
            "title": "1:1 Architecture Sync w/ Sarah",
            "location": "Meet / Room 4B",
            "status": "up_next",
            "calendar": "Work",
        },
        {
            "time": "12:30 - 13:30",
            "title": "Lunch & Walk Outside",
            "location": "Local Park",
            "status": "upcoming",
            "calendar": "Personal",
        },
        {
            "time": "14:00 - 15:00",
            "title": "Platform Reliability Review",
            "location": "Zoom",
            "status": "upcoming",
            "calendar": "Work",
        },
        {
            "time": "17:30 - 18:30",
            "title": "Strength Training / Gym Session",
            "location": "Equinox",
            "status": "upcoming",
            "calendar": "Health",
        },
        {
            "time": "20:00 - 21:00",
            "title": "Weekly Family Planning & Budget Check",
            "location": "Home",
            "status": "upcoming",
            "calendar": "Family",
        },
    ],
    "habits": [
        {"name": "Deep Work (2h uninterrupted)", "streak": 12, "done_today": True},
        {"name": "Hydration (2.5L water)", "streak": 8, "done_today": True},
        {"name": "Zero Inbox Triage", "streak": 5, "done_today": False},
        {"name": "30m Exercise / 10k Steps", "streak": 19, "done_today": False},
    ],
    "world_clocks": [
        {"label": "SF / Local", "tz": "America/Los_Angeles"},
        {"label": "New York", "tz": "America/New_York"},
        {"label": "London / UTC", "tz": "UTC"},
        {"label": "Tokyo", "tz": "Asia/Tokyo"},
    ],
}


def get_default_config_path() -> Path:
    """Return standard XDG / home config file path."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "daily-dash" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load user YAML configuration merged over DEFAULT_CONFIG."""
    import copy

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


def write_sample_config(target_path: str | Path) -> Path:
    """Write a documented starter config.yaml to disk."""
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(DEFAULT_CONFIG, fh, sort_keys=False, allow_unicode=True)
    return path
