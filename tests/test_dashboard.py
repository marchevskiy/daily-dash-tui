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
    assert len(loaded["google_home_devices"]) >= 4
    assert len(loaded["tasks"]) >= 3


def test_network_discovery_helpers() -> None:
    local_ip, subnet = get_local_ip_and_subnet()
    assert "." in local_ip
    assert "/24" in subnet

    neighbors = parse_arp_neighbors()
    assert isinstance(neighbors, list)

    scan_res = scan_network(max_hosts=4, timeout=0.05)
    assert "managed_hosts" in scan_res
    assert "google_home_devices" in scan_res
    assert len(scan_res["managed_hosts"]) >= 1


def test_google_sync_time_formatter() -> None:
    label, s_dt, e_dt = _format_event_window(
        "2026-11-25T15:30:00-08:00",
        "2026-11-25T16:00:00-08:00",
    )
    assert label == "15:30 - 16:00"
    assert s_dt is not None and e_dt is not None


def test_providers_metrics_and_clocks() -> None:
    metrics = collect_system_metrics("Alex-MacBook-Pro.local")
    assert metrics.hostname == "Alex-MacBook-Pro.local"
    assert 0.0 <= metrics.cpu_total_pct <= 100.0
    assert metrics.mem_total_gb > 0

    weather = get_fallback_weather("San Francisco, CA", "fahrenheit")
    assert weather.unit_symbol == "°F"
    assert len(weather.forecast) == 3

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
async def test_tui_panes_and_interactions() -> None:
    cfg = load_config()
    app = DailyDashApp(config=cfg, offline=True)
    async with app.run_test(size=(140, 42)) as pilot:
        sys_pane = app.query_one("#pane-system", SystemMonitorPane)
        home_pane = app.query_one("#pane-home", SmartHomePane)
        weather_pane = app.query_one("#pane-weather", WeatherPane)
        tasks_pane = app.query_one("#pane-tasks", TasksEmailPane)
        cal_pane = app.query_one("#pane-calendar", CalendarPane)
        extras_pane = app.query_one("#pane-extras", CommunityExtrasPane)

        assert sys_pane is not None
        assert weather_pane is not None
        assert cal_pane is not None

        # Focus pane 2 (Smart Home) and toggle a device
        await pilot.press("2")
        assert app.focused == home_pane
        initial_state = home_pane.devices[0]["active"]
        await pilot.press("space")
        assert home_pane.devices[0]["active"] is not initial_state

        # Focus pane 4 (Tasks & Email) and toggle task completion
        await pilot.press("4")
        assert app.focused == tasks_pane
        initial_done = tasks_pane.tasks[0]["done"]
        await pilot.press("space")
        assert tasks_pane.tasks[0]["done"] is not initial_done

        # Focus pane 6 (Extras) and start Pomodoro timer
        await pilot.press("6")
        assert app.focused == extras_pane
        assert extras_pane.pomo_running is False
        await pilot.press("p")
        assert extras_pane.pomo_running is True

        # Test zooming & unzooming pane
        await pilot.press("z")
        assert extras_pane.has_class("maximized")
        assert sys_pane.has_class("hidden-pane")
        await pilot.press("z")
        assert not extras_pane.has_class("maximized")
        assert not sys_pane.has_class("hidden-pane")
