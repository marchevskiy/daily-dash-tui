"""Main Textual application for DailyDash TUI."""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.widgets import Footer, Header

from daily_dash.config import load_config
from daily_dash.providers import fetch_weather_async
from daily_dash.widgets import (
    CalendarPane,
    CommunityExtrasPane,
    SmartHomePane,
    SystemMonitorPane,
    TasksEmailPane,
    WeatherPane,
)


class DailyDashApp(App[None]):
    """Multi-pane terminal dashboard for daily life."""

    TITLE = "DailyDash TUI"
    SUB_TITLE = "MacBook & Fleet • Google Home • Tasks & Inbox • Calendar • Weather • Focus & Git"

    CSS = """
    Screen {
        background: #090d16;
        color: #f8fafc;
    }

    #dashboard-grid {
        grid-size: 3 2;
        grid-gutter: 1 1;
        padding: 0 1;
        width: 100%;
        height: 1fr;
    }

    .maximized {
        column-span: 3;
        row-span: 2;
    }

    .hidden-pane {
        display: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh_all", "Refresh All", show=True),
        Binding("z", "toggle_zoom", "Zoom Pane", show=True),
        Binding("1", "focus_pane('pane-system')", "1:System", show=True),
        Binding("2", "focus_pane('pane-home')", "2:Home", show=True),
        Binding("3", "focus_pane('pane-weather')", "3:Weather", show=True),
        Binding("4", "focus_pane('pane-tasks')", "4:Tasks/Mail", show=True),
        Binding("5", "focus_pane('pane-calendar')", "5:Calendar", show=True),
        Binding("6", "focus_pane('pane-extras')", "6:Focus/Git", show=True),
    ]

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        offline: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config or load_config()
        self.offline = offline
        self._zoomed_pane_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Grid(id="dashboard-grid"):
            yield SystemMonitorPane(self.config, id="pane-system")
            yield SmartHomePane(self.config, id="pane-home")
            yield WeatherPane(self.config, id="pane-weather")
            yield TasksEmailPane(self.config, id="pane-tasks")
            yield CalendarPane(self.config, id="pane-calendar")
            yield CommunityExtrasPane(self.config, id="pane-extras")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#pane-system").focus()
        intervals = self.config.get("refresh_intervals", {})
        sys_sec = float(intervals.get("system_metrics_sec", 2.0))
        self.set_interval(sys_sec, self._tick_system)
        self.set_interval(1.0, self._tick_second)
        if not self.offline:
            self.run_worker(self._refresh_weather(), exclusive=True)

    def _tick_system(self) -> None:
        self.query_one(SystemMonitorPane).refresh_metrics()

    def _tick_second(self) -> None:
        self.query_one(CommunityExtrasPane).tick_second()

    async def _refresh_weather(self) -> None:
        prof = self.config.get("profile", {})
        report = await fetch_weather_async(
            location=prof.get("location", "San Francisco, CA"),
            latitude=float(prof.get("latitude", 37.7749)),
            longitude=float(prof.get("longitude", -122.4194)),
            unit=prof.get("temperature_unit", "fahrenheit"),
        )
        self.query_one(WeatherPane).update_weather(report)

    def action_focus_pane(self, pane_id: str) -> None:
        if self._zoomed_pane_id and self._zoomed_pane_id != pane_id:
            self._unzoom_all()
        target = self.query_one(f"#{pane_id}")
        target.focus()

    def action_toggle_zoom(self) -> None:
        focused = self.focused
        if focused is None or not focused.id or not focused.id.startswith("pane-"):
            return
        if self._zoomed_pane_id == focused.id:
            self._unzoom_all()
        else:
            self._zoom_pane(focused.id)

    def _zoom_pane(self, pane_id: str) -> None:
        self._zoomed_pane_id = pane_id
        for pane in self.query("#dashboard-grid > *"):
            if pane.id == pane_id:
                pane.remove_class("hidden-pane")
                pane.add_class("maximized")
            else:
                pane.remove_class("maximized")
                pane.add_class("hidden-pane")

    def _unzoom_all(self) -> None:
        self._zoomed_pane_id = None
        for pane in self.query("#dashboard-grid > *"):
            pane.remove_class("maximized")
            pane.remove_class("hidden-pane")

    def action_refresh_all(self) -> None:
        self.query_one(SystemMonitorPane).refresh_metrics()
        self.query_one(CommunityExtrasPane).tick_second()
        if not self.offline:
            self.run_worker(self._refresh_weather(), exclusive=True)
