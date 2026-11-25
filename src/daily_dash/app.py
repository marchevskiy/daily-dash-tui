"""Main Textual application for DailyDash TUI."""

from __future__ import annotations

import asyncio
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.widgets import Footer, Header

from daily_dash.config import load_config, save_config
from daily_dash.discovery import scan_network
from daily_dash.google_sync import sync_config_with_google
from daily_dash.providers import fetch_weather_async
from daily_dash.widgets import (
    CalendarPane,
    CommunityExtrasPane,
    ResponsivePane,
    SmartHomePane,
    SystemMonitorPane,
    TasksEmailPane,
    WeatherPane,
)


class DailyDashApp(App[None]):
    """Multi-pane terminal dashboard for daily life."""

    TITLE = "DailyDash TUI"
    SUB_TITLE = "MacBook & Fleet • SF Smart Home • Weather & Tides • Tasks & Inbox • Family Calendar • Automations"

    CSS = """
    Screen {
        background: #090d16;
        color: #f8fafc;
    }

    #dashboard-grid {
        grid-size: 3 2;
        grid-columns: 1fr 1fr 1fr;
        grid-rows: 1fr 1fr;
        grid-gutter: 1 1;
        padding: 0 1;
        width: 100%;
        height: 1fr;
    }

    #dashboard-grid.zoomed {
        grid-size: 1 1;
        grid-columns: 1fr;
        grid-rows: 1fr;
    }

    .maximized {
        width: 100%;
        height: 100%;
    }

    .hidden-pane {
        display: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh_all", "Refresh", show=True),
        Binding("g", "sync_google", "Sync Google", show=True),
        Binding("s", "scan_lan", "Scan LAN", show=True),
        Binding("z", "toggle_zoom", "Zoom Pane", show=True),
        Binding("1", "focus_pane('pane-system')", "1:System", show=True),
        Binding("2", "focus_pane('pane-home')", "2:Home", show=True),
        Binding("3", "focus_pane('pane-weather')", "3:Weather/Tides", show=True),
        Binding("4", "focus_pane('pane-tasks')", "4:Tasks/Mail", show=True),
        Binding("5", "focus_pane('pane-calendar')", "5:Calendar", show=True),
        Binding("6", "focus_pane('pane-extras')", "6:Automations", show=True),
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
        for pane in self.query(SystemMonitorPane):
            pane.refresh_metrics()

    def _tick_second(self) -> None:
        for pane in self.query(CommunityExtrasPane):
            pane.tick_second()

    async def _refresh_weather(self) -> None:
        prof = self.config.get("profile", {})
        report = await fetch_weather_async(
            location=prof.get("location", "San Francisco, CA"),
            latitude=float(prof.get("latitude", 37.7749)),
            longitude=float(prof.get("longitude", -122.4194)),
            unit=prof.get("temperature_unit", "fahrenheit"),
            tide_station_id=str(prof.get("tide_station_id", "9414290")),
            tide_station_name=str(
                prof.get("tide_station_name", "San Francisco (Golden Gate / Ocean Beach)")
            ),
        )
        for pane in self.query(WeatherPane):
            pane.update_weather(report)

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
        grid = self.query_one("#dashboard-grid", Grid)
        grid.add_class("zoomed")
        for pane in self.query("#dashboard-grid > *"):
            if pane.id == pane_id:
                pane.remove_class("hidden-pane")
                pane.add_class("maximized")
                if isinstance(pane, ResponsivePane):
                    pane.refresh_view()
            else:
                pane.remove_class("maximized")
                pane.add_class("hidden-pane")

    def _unzoom_all(self) -> None:
        self._zoomed_pane_id = None
        grid = self.query_one("#dashboard-grid", Grid)
        grid.remove_class("zoomed")
        for pane in self.query("#dashboard-grid > *"):
            pane.remove_class("maximized")
            pane.remove_class("hidden-pane")
            if isinstance(pane, ResponsivePane):
                pane.refresh_view()

    def action_refresh_all(self) -> None:
        self.query_one(SystemMonitorPane).refresh_metrics()
        self.query_one(CommunityExtrasPane).tick_second()
        if not self.offline:
            self.run_worker(self._refresh_weather(), exclusive=True)
            self.run_worker(self._worker_refresh_smart_home(), exclusive=False)

    async def _worker_refresh_smart_home(self) -> None:
        from daily_dash.discovery import refresh_smart_devices_telemetry

        await asyncio.to_thread(
            refresh_smart_devices_telemetry,
            self.config.get("google_home_devices", []),
        )
        for pane in self.query(SmartHomePane):
            pane.refresh_view()

    def action_sync_google(self) -> None:
        self.notify("Syncing Google Calendar, Tasks & Apps Script Automations...", title="Google Workspace")
        self.run_worker(self._worker_sync_google(), exclusive=False)

    async def _worker_sync_google(self) -> None:
        await asyncio.to_thread(sync_config_with_google, self.config)
        await asyncio.to_thread(save_config, self.config)
        self.query_one(TasksEmailPane).reload_tasks(self.config.get("tasks", []))
        self.query_one(CalendarPane).reload_events(self.config.get("calendar_events", []))
        self.query_one(CommunityExtrasPane).reload_automations(self.config.get("automations", []))
        self.notify(
            f"Synced {len(self.config.get('calendar_events', []))} events, "
            f"{len(self.config.get('tasks', []))} tasks & "
            f"{len(self.config.get('automations', []))} automations",
            title="Google Sync Complete",
        )

    def action_scan_lan(self) -> None:
        self.notify("Scanning local network (mDNS / ARP / Cast / Matter)...", title="LAN Discovery")
        self.run_worker(self._worker_scan_lan(), exclusive=False)

    async def _worker_scan_lan(self) -> None:
        res = await asyncio.to_thread(scan_network)
        if res.get("google_home_devices"):
            existing_names = {d["name"] for d in res["google_home_devices"]}
            self.config["google_home_devices"] = (
                list(res["google_home_devices"])
                + [d for d in self.config.get("google_home_devices", []) if d["name"] not in existing_names]
            )[:10]
        if res.get("managed_hosts"):
            existing_ips = {h.get("ip") for h in res["managed_hosts"]}
            self.config["managed_hosts"] = (
                list(res["managed_hosts"])
                + [h for h in self.config.get("managed_hosts", []) if h.get("ip") not in existing_ips]
            )[:8]
        await asyncio.to_thread(save_config, self.config)
        self.query_one(SmartHomePane).reload_devices(self.config.get("google_home_devices", []))
        self.query_one(SystemMonitorPane).refresh_metrics()
        self.notify(
            f"Discovered {len(res.get('managed_hosts', []))} hosts & {len(res.get('google_home_devices', []))} smart devices on {res.get('subnet')}",
            title="LAN Scan Complete",
        )
