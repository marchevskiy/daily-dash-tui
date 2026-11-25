"""Tests for DailyDash TUI."""

from __future__ import annotations

from pathlib import Path

import pytest

from daily_dash.app import DailyDashApp
from daily_dash.cli import build_parser, main
from daily_dash.config import load_config, write_sample_config
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
    write_sample_config(sample_file)
    assert sample_file.exists()

    loaded = load_config(sample_file)
    assert loaded["profile"]["primary_host"] == "MacBook-Pro-M3.local"
    assert len(loaded["google_home_devices"]) >= 4
    assert len(loaded["tasks"]) >= 3


def test_providers_metrics_and_clocks() -> None:
    metrics = collect_system_metrics("MacBook-Pro-M3.local")
    assert metrics.hostname == "MacBook-Pro-M3.local"
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
    rc = main(["--init-config", "--config", str(cfg_path)])
    assert rc == 0
    assert cfg_path.exists()


@pytest.mark.asyncio
async def test_tui_panes_and_interactions() -> None:
    cfg = load_config()
    app = DailyDashApp(config=cfg, offline=True)
    async with app.run_test(size=(140, 42)) as pilot:
        # Verify all 6 panes exist
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
