"""Tests for DailyDash TUI."""

from __future__ import annotations

from pathlib import Path

import pytest

from daily_dash.app import DailyDashApp
from daily_dash.cli import main
from daily_dash.config import load_config, write_sample_config
from daily_dash.discovery import get_local_ip_and_subnet, parse_arp_neighbors, scan_network
from daily_dash.google_sync import _format_event_window
from daily_dash.providers import (
    collect_system_metrics,
    get_fallback_tides,
    get_fallback_weather,
    get_git_dev_pulse,
    get_world_clock_strings,
)
from daily_dash.widgets import (
    CalendarPane,
    CommunityExtrasPane,
    SmartHomePane,
    SystemMonitorPane,
    TasksEmailPane,
    WeatherPane,
)


def test_config_roundtrip(tmp_path: Path) -> None:
    sample_file = tmp_path / "config.yaml"
    write_sample_config(sample_file, sync_google=False, scan_lan=False)
    assert sample_file.exists()

    loaded = load_config(sample_file)
    assert loaded["profile"]["primary_host"] == "Alex-MacBook-Pro.local"
    assert loaded["profile"]["tide_station_id"] == "9414290"
    assert len(loaded["automations"]) == 4
    # Only the single Nest Thermostat is in default config before LAN scan (no fake smoke detectors/locks)
    assert len(loaded["google_home_devices"]) == 1
    assert loaded["google_home_devices"][0]["name"] == "Nest Thermostat"
    assert len(loaded["tasks"]) >= 3


def test_network_discovery_helpers() -> None:
    from daily_dash.config import DEFAULT_CONFIG, merge_discovered_devices

    local_ip, subnet = get_local_ip_and_subnet()
    assert "." in local_ip
    assert "/24" in subnet

    neighbors = parse_arp_neighbors()
    assert isinstance(neighbors, list)

    scan_res = scan_network(max_hosts=4, timeout=0.05)
    assert "managed_hosts" in scan_res
    assert "google_home_devices" in scan_res
    assert len(scan_res["managed_hosts"]) >= 1

    # Verify that discovering 2 physical LAN speakers yields ONLY the Nest Thermostat + 2 real speakers
    two_real_speakers = [
        {"id": "cast-1", "name": "Office Speaker", "room": "Office", "type": "speaker", "volume_pct": 50},
        {"id": "cast-2", "name": "Bedroom Speaker", "room": "Bedroom", "type": "speaker", "volume_pct": 35},
    ]
    merged = merge_discovered_devices(DEFAULT_CONFIG["google_home_devices"], two_real_speakers)
    assert len(merged) == 3
    assert merged[0]["type"] == "thermostat"
    assert merged[0]["name"] == "Nest Thermostat"
    speakers_in_merged = [d for d in merged if d["type"] == "speaker"]
    assert len(speakers_in_merged) == 2
    assert [s["name"] for s in speakers_in_merged] == ["Office Speaker", "Bedroom Speaker"]


def test_google_sync_time_formatter() -> None:
    label, s_dt, e_dt = _format_event_window(
        "2026-11-25T15:30:00-08:00",
        "2026-11-25T16:00:00-08:00",
    )
    assert label == "15:30 - 16:00"
    assert s_dt is not None and e_dt is not None


def test_providers_metrics_tides_and_clocks() -> None:
    metrics = collect_system_metrics("Alex-MacBook-Pro.local")
    assert metrics.hostname == "Alex-MacBook-Pro.local"
    assert 0.0 <= metrics.cpu_total_pct <= 100.0
    assert metrics.mem_total_gb > 0

    tides = get_fallback_tides()
    assert tides.station_id == "9414290"
    assert len(tides.events) == 4

    weather = get_fallback_weather("San Francisco, CA", "fahrenheit")
    assert weather.unit_symbol == "°F"
    assert len(weather.forecast) >= 3
    assert weather.tides is not None
    assert weather.tides.station_id == "9414290"

    clocks = get_world_clock_strings([{"label": "UTC", "tz": "UTC"}])
    assert len(clocks) == 1
    assert clocks[0][0] == "UTC"

    git_pulse = get_git_dev_pulse()
    assert "repo" in git_pulse
    assert "branch" in git_pulse


def test_cli_init_config(tmp_path: Path) -> None:
    cfg_path = tmp_path / "custom.yaml"
    rc = main(["--init-config", "--offline", "--config", str(cfg_path)])
    assert rc == 0
    assert cfg_path.exists()


@pytest.mark.asyncio
async def test_tui_panes_and_dynamic_zoom() -> None:
    import copy
    from daily_dash.config import DEFAULT_CONFIG

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["google_home_devices"].append(
        {
            "id": "cast-test-1",
            "name": "Living Room Speaker",
            "room": "Living Room",
            "type": "speaker",
            "volume_pct": 40,
            "muted": False,
            "media": "Idle",
            "state": "Idle • Vol 40%",
            "online": True,
            "active": True,
        }
    )
    app = DailyDashApp(config=cfg, offline=True)
    async with app.run_test(size=(150, 44)) as pilot:
        sys_pane = app.query_one("#pane-system", SystemMonitorPane)
        home_pane = app.query_one("#pane-home", SmartHomePane)
        weather_pane = app.query_one("#pane-weather", WeatherPane)
        tasks_pane = app.query_one("#pane-tasks", TasksEmailPane)
        cal_pane = app.query_one("#pane-calendar", CalendarPane)
        extras_pane = app.query_one("#pane-extras", CommunityExtrasPane)

        assert sys_pane is not None
        assert weather_pane.report.tides is not None
        assert len(extras_pane.automations) == 4
        assert cal_pane is not None

        # Focus pane 2 (Smart Home), toggle Nest Thermostat (index 0), and adjust target temperature with +
        await pilot.press("2")
        assert app.focused == home_pane
        assert home_pane.devices[0]["type"] == "thermostat"
        initial_state = home_pane.devices[0]["active"]
        await pilot.press("space")
        assert home_pane.devices[0]["active"] is not initial_state
        initial_target = float(home_pane.devices[0]["target_f"])
        await pilot.press("+")
        assert float(home_pane.devices[0]["target_f"]) == initial_target + 1.0

        # Navigate down to Kitchen Nest Speaker (index 1) and adjust volume + mute
        await pilot.press("j")
        assert home_pane.devices[home_pane.selected_idx]["type"] == "speaker"
        initial_vol = int(home_pane.devices[home_pane.selected_idx]["volume_pct"])
        await pilot.press("+")
        assert int(home_pane.devices[home_pane.selected_idx]["volume_pct"]) == min(100, initial_vol + 5)
        await pilot.press("m")
        assert home_pane.devices[home_pane.selected_idx]["muted"] is True

        # Focus pane 4 (Tasks & Email) and toggle task completion
        await pilot.press("4")
        assert app.focused == tasks_pane
        initial_done = tasks_pane.tasks[0]["done"]
        await pilot.press("space")
        assert tasks_pane.tasks[0]["done"] is not initial_done

        # Focus pane 6 (Extras / Automations) and start Pomodoro timer
        await pilot.press("6")
        assert app.focused == extras_pane
        assert extras_pane.pomo_running is False
        await pilot.press("p")
        assert extras_pane.pomo_running is True

        # Test zooming & unzooming pane — verify grid switches to 1x1 zoomed class and pane expands
        await pilot.press("z")
        await pilot.pause(0.1)
        grid = app.query_one("#dashboard-grid")
        assert grid.has_class("zoomed")
        assert extras_pane.has_class("maximized")
        assert sys_pane.has_class("hidden-pane")
        assert extras_pane.size.width > 120
        assert extras_pane.size.height > 35

        await pilot.press("z")
        await pilot.pause(0.1)
        assert not grid.has_class("zoomed")
        assert not extras_pane.has_class("maximized")
        assert not sys_pane.has_class("hidden-pane")
