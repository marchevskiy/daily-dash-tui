"""Responsive Textual pane widgets for DailyDash TUI."""

from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static

from daily_dash.providers import (
    SystemMetrics,
    WeatherReport,
    collect_system_metrics,
    get_fallback_weather,
    get_git_dev_pulse,
    get_world_clock_strings,
)


def _render_bar(pct: float, width: int = 18) -> Text:
    """Render an htop-style color-coded progress bar that scales to width."""
    bar_w = max(8, width)
    clamped = max(0.0, min(100.0, pct))
    filled = int(round((clamped / 100.0) * bar_w))
    empty = max(0, bar_w - filled)
    if clamped < 60:
        color = "bright_green"
    elif clamped < 85:
        color = "bright_yellow"
    else:
        color = "bright_red"

    bar = Text("[", style="dim")
    bar.append("█" * filled, style=color)
    bar.append("░" * empty, style="grey35")
    bar.append(f"] {clamped:5.1f}%", style=f"bold {color}")
    return bar


def _pane_divider(style: str = "grey27") -> Rule:
    """Full-width horizontal divider that automatically stretches to pane width."""
    return Rule(style=style, characters="─")


class ResponsivePane(Static, can_focus=True):
    """Base pane that tracks its dynamic width/height and re-renders on resize or zoom."""

    def _dims(self) -> tuple[int, int, bool]:
        w = self.size.width if self.size.width > 10 else 48
        h = self.size.height if self.size.height > 6 else 18
        is_zoomed = self.has_class("maximized") or w >= 90 or h >= 28
        return w, h, is_zoomed

    def on_resize(self, event: events.Resize) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        self.update(self._build_renderable())

    def _build_renderable(self) -> Group:
        return Group()


class SystemMonitorPane(ResponsivePane):
    """Pane 1: Simplified htop & MacBook / Managed Fleet Monitor."""

    DEFAULT_CSS = """
    SystemMonitorPane {
        border: round #38bdf8;
        padding: 0 1;
        width: 100%;
        height: 100%;
        background: #0f172a;
    }
    SystemMonitorPane:focus {
        border: double #7dd3fc;
        background: #131c31;
    }
    """

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = " 💻 MacBook & Fleet Monitor (htop) "
        self.config = config
        self.metrics: SystemMetrics = collect_system_metrics(
            config.get("profile", {}).get("primary_host")
        )

    def refresh_metrics(self) -> None:
        self.metrics = collect_system_metrics(
            self.config.get("profile", {}).get("primary_host"),
            max_procs=25,
        )
        self.refresh_view()

    def on_mount(self) -> None:
        self.refresh_metrics()

    def _build_renderable(self) -> Group:
        w, h, is_zoomed = self._dims()
        m = self.metrics
        bar_w = max(12, min(64, w - 26))

        header = Text()
        header.append(f"Host: {m.hostname} ", style="bold cyan")
        header.append(f"• Up {m.uptime_str} ", style="grey70")
        batt_icon = "⚡" if m.power_plugged else "🔋"
        header.append(f"• {batt_icon} {m.battery_pct:.0f}%", style="bold green")
        if is_zoomed:
            header.append(f"  •  {m.os_summary}", style="grey62")

        gauges = Table.grid(padding=(0, 1), expand=True)
        gauges.add_column(style="bold white", width=5)
        gauges.add_column(ratio=1)
        gauges.add_column(style="dim", justify="right", width=16)

        gauges.add_row(
            "CPU",
            _render_bar(m.cpu_total_pct, bar_w),
            f"Load {m.load_avg[0]:.2f} {m.load_avg[1]:.2f}",
        )
        gauges.add_row(
            "MEM",
            _render_bar(m.mem_pct, bar_w),
            f"{m.mem_used_gb}/{m.mem_total_gb}G (Swp {m.swap_pct:.0f}%)",
        )
        gauges.add_row(
            "DSK",
            _render_bar(m.disk_pct, bar_w),
            f"{m.disk_used_gb:.0f}/{m.disk_total_gb:.0f}G",
        )

        # Per-core mini spark strip
        core_line = Text("Cores: ", style="dim")
        blocks = " ▂▃▄▅▆▇█"
        max_cores = 24 if is_zoomed else 12
        for c in m.cpu_cores_pct[:max_cores]:
            idx = min(len(blocks) - 1, int((c / 100.0) * (len(blocks) - 1)))
            col = "green" if c < 60 else ("yellow" if c < 85 else "red")
            core_line.append(blocks[idx], style=f"bold {col}")
        core_line.append(f"   Net ↑{m.net_sent_mb:.1f}MB ↓{m.net_recv_mb:.1f}MB", style="grey70")

        # Dynamically calculate how many process rows fit the available height
        reserved_rows = 12 if is_zoomed else 9
        max_proc_rows = max(4, min(len(m.top_processes), h - reserved_rows))

        proc_table = Table(
            show_header=True,
            header_style="bold #38bdf8",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        proc_table.add_column("PID", style="dim", width=7)
        proc_table.add_column("PROCESS", style="white", ratio=1)
        if is_zoomed:
            proc_table.add_column("STATE", style="grey70", width=8)
        proc_table.add_column("CPU%", justify="right", width=7)
        proc_table.add_column("MEM%", justify="right", width=7)

        for p in m.top_processes[:max_proc_rows]:
            c_style = "bold red" if p.cpu_pct > 50 else ("yellow" if p.cpu_pct > 15 else "green")
            if is_zoomed:
                proc_table.add_row(
                    str(p.pid),
                    p.name,
                    p.status,
                    Text(f"{p.cpu_pct:5.1f}", style=c_style),
                    f"{p.mem_pct:5.1f}",
                )
            else:
                proc_table.add_row(
                    str(p.pid),
                    p.name[:22],
                    Text(f"{p.cpu_pct:4.1f}", style=c_style),
                    f"{p.mem_pct:4.1f}",
                )

        # Managed Fleet section: full table when zoomed, compact strip in grid mode
        hosts = self.config.get("managed_hosts", [])
        if is_zoomed and hosts:
            fleet_tbl = Table(
                show_header=True,
                header_style="bold cyan",
                box=None,
                padding=(0, 1),
                expand=True,
            )
            fleet_tbl.add_column("MANAGED HOST", style="bold white", ratio=1)
            fleet_tbl.add_column("IP ADDRESS", style="cyan", width=16)
            fleet_tbl.add_column("ROLE / DETAILS", style="grey78", ratio=1)
            fleet_tbl.add_column("METRICS", justify="right", width=22)
            for host in hosts:
                h_cpu = host.get("cpu_pct")
                h_mem = host.get("mem_pct")
                metric_str = (
                    f"CPU {h_cpu:.1f}% • MEM {h_mem:.1f}%"
                    if h_cpu is not None
                    else f"⚡ Batt {host.get('battery_pct', 92)}%"
                )
                fleet_tbl.add_row(
                    f"● {host.get('hostname', '')}",
                    str(host.get("ip", "")),
                    str(host.get("role", "")),
                    Text(metric_str, style="green"),
                )
            return Group(header, gauges, core_line, _pane_divider(), proc_table, _pane_divider(), fleet_tbl)

        fleet_line = Text("Fleet: ", style="bold #38bdf8")
        for host in hosts[1:4]:
            h_name = host.get("hostname", "").split(".")[0]
            h_cpu = host.get("cpu_pct", 0.0)
            fleet_line.append(f"● {h_name} ", style="green")
            fleet_line.append(f"({h_cpu:.0f}% CPU)  ", style="grey70")

        return Group(header, gauges, core_line, _pane_divider(), proc_table, _pane_divider(), fleet_line)


class SmartHomePane(ResponsivePane):
    """Pane 2: Google Home & Matter Connected Devices with interactive toggle."""

    BINDINGS = [
        Binding("j,down", "cursor_down", "Next Device", show=False),
        Binding("k,up", "cursor_up", "Prev Device", show=False),
        Binding("space,enter", "toggle_device", "Toggle Device", show=True),
    ]

    DEFAULT_CSS = """
    SmartHomePane {
        border: round #34d399;
        padding: 0 1;
        width: 100%;
        height: 100%;
        background: #0f172a;
    }
    SmartHomePane:focus {
        border: double #6ee7b7;
        background: #112224;
    }
    """

    selected_idx: reactive[int] = reactive(0)

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = " 🏠 Google Home & SF Smart Devices [Space: Toggle | s: Scan LAN] "
        self.devices: list[dict[str, Any]] = list(config.get("google_home_devices", []))

    def reload_devices(self, devices: list[dict[str, Any]]) -> None:
        self.devices = list(devices)
        self.selected_idx = 0
        self.refresh_view()

    def on_mount(self) -> None:
        self.refresh_view()

    def watch_selected_idx(self) -> None:
        self.refresh_view()

    def action_cursor_down(self) -> None:
        if self.devices:
            self.selected_idx = (self.selected_idx + 1) % len(self.devices)

    def action_cursor_up(self) -> None:
        if self.devices:
            self.selected_idx = (self.selected_idx - 1) % len(self.devices)

    def action_toggle_device(self) -> None:
        if not self.devices:
            return
        dev = self.devices[self.selected_idx]
        dev["active"] = not dev.get("active", True)
        dtype = dev.get("type", "device")
        if dtype == "light":
            dev["state"] = "On • 85% Warm White (90+ CRI)" if dev["active"] else "Off • Standby"
        elif dtype == "lock":
            dev["state"] = "Locked • Battery 94%" if dev["active"] else "Unlocked • Manual"
        elif dtype == "speaker":
            dev["state"] = "Playing • Nest Audio Cast" if dev["active"] else "Idle • Ready to Cast"
        elif dtype == "thermostat":
            dev["state"] = "Heating • 69°F → 70°F" if dev["active"] else "Eco Mode • 64°F"
        else:
            dev["state"] = "Active • All Clear" if dev["active"] else "Standby • Muted"
        self.refresh_view()

    def _build_renderable(self) -> Group:
        _, h, is_zoomed = self._dims()
        active_count = sum(1 for d in self.devices if d.get("active"))
        summary = Text()
        summary.append("SF Rowhouse Hub: ", style="bold #34d399")
        summary.append(f"{len(self.devices)} online • {active_count} active ", style="white")
        summary.append("• Mesh: 610 Mbps", style="grey70")

        table = Table(
            show_header=True,
            header_style="bold #34d399",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("", width=2)
        table.add_column("DEVICE", ratio=2)
        table.add_column("ROOM / ZONE", style="grey70", ratio=1)
        if is_zoomed:
            table.add_column("TYPE", style="cyan", width=12)
        table.add_column("STATE", ratio=2)

        icons = {
            "thermostat": "🌡️",
            "light": "💡",
            "speaker": "🔊",
            "lock": "🔒",
            "air": "🍃",
        }

        max_rows = len(self.devices) if is_zoomed else max(5, h - 6)
        for idx, dev in enumerate(self.devices[:max_rows]):
            is_sel = idx == self.selected_idx
            pointer = "▸" if is_sel else " "
            icon = icons.get(dev.get("type", ""), "📟")
            active = dev.get("active", False)
            dot_style = "bold bright_green" if active else "grey50"
            name_style = "bold reverse" if is_sel else ("bold white" if active else "grey62")
            state_style = "bright_green" if active else "grey58"

            if is_zoomed:
                table.add_row(
                    Text(pointer, style="bold #34d399"),
                    Text(f"{icon} {dev.get('name', 'Device')}", style=name_style),
                    str(dev.get("room", "")),
                    str(dev.get("type", "smart")).upper(),
                    Text(f"● {dev.get('state', '')}", style=state_style if active else dot_style),
                )
            else:
                table.add_row(
                    Text(pointer, style="bold #34d399"),
                    Text(f"{icon} {dev.get('name', 'Device')}", style=name_style),
                    str(dev.get("room", "")),
                    Text(f"● {dev.get('state', '')}", style=state_style if active else dot_style),
                )

        footer = Text(
            "↑/↓ (or j/k) + Space: Toggle device  •  Press 's' to scan LAN for Google Cast/Matter devices",
            style="italic grey50",
        )
        return Group(summary, _pane_divider(), table, _pane_divider(), footer)


class WeatherPane(ResponsivePane):
    """Pane 3: Live Weather, 3-5 Day Forecast, and Local NOAA San Francisco Tides."""

    DEFAULT_CSS = """
    WeatherPane {
        border: round #fbbf24;
        padding: 0 1;
        width: 100%;
        height: 100%;
        background: #0f172a;
    }
    WeatherPane:focus {
        border: double #fde68a;
        background: #1e1b18;
    }
    """

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = " 🌦️ SF Weather & 🌊 Local NOAA Tides "
        prof = config.get("profile", {})
        self.report: WeatherReport = get_fallback_weather(
            prof.get("location", "San Francisco, CA"),
            prof.get("temperature_unit", "fahrenheit"),
            prof.get("tide_station_id", "9414290"),
            prof.get("tide_station_name", "San Francisco (Golden Gate / Ocean Beach)"),
        )

    def update_weather(self, report: WeatherReport) -> None:
        self.report = report
        self.refresh_view()

    def on_mount(self) -> None:
        self.refresh_view()

    def _build_renderable(self) -> Group:
        _, h, is_zoomed = self._dims()
        w = self.report
        badge = "LIVE" if w.is_live else "CACHED"
        badge_style = "bold bright_green" if w.is_live else "bold yellow"

        top = Text()
        top.append(f"{w.icon}  {w.temp:.1f}{w.unit_symbol} ", style="bold bright_yellow")
        top.append(f"{w.condition} ", style="bold white")
        top.append(f"[{badge}]  ", style=badge_style)
        top.append(f"📍 {w.location} (Feels {w.feels_like:.1f}{w.unit_symbol})", style="grey78")

        details = Table.grid(padding=(0, 2), expand=True)
        details.add_column(ratio=1)
        details.add_column(ratio=1)
        details.add_row(
            Text(f"💧 Humidity: {w.humidity}%  •  💨 Wind: {w.wind_mph:.1f} mph", style="cyan"),
            Text(f"🌅 Sun: {w.sunrise} → 🌇 {w.sunset} (Walk Kosmo!)", style="bold #fbbf24"),
        )
        if is_zoomed or h >= 18:
            details.add_row(
                Text(f"☀️ UV Index: {w.uv_index}", style="yellow"),
                Text(f"🍃 AQI: {w.aqi} (Good)", style="green"),
            )

        # NOAA Local Tides Section
        tides = w.tides
        tide_hdr = Text()
        tide_hdr.append("🌊 Local Tides ", style="bold bright_cyan")
        if tides:
            t_badge = "NOAA LIVE" if tides.is_live else "NOAA 9414290"
            tide_hdr.append(f"({tides.station_name} • {t_badge}): ", style="grey70")
            tide_hdr.append(tides.state_summary, style="bold cyan")

        tide_table = Table(
            show_header=is_zoomed,
            header_style="bold bright_cyan",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        tide_table.add_column("TIDE", width=9)
        tide_table.add_column("TIME", width=8)
        tide_table.add_column("HEIGHT (MLLW)", justify="right", width=13)
        tide_table.add_column("VISUAL", ratio=1)

        if tides:
            max_tide_rows = 6 if is_zoomed else 4
            for ev in tides.events[:max_tide_rows]:
                is_high = ev.type == "HIGH"
                t_icon = "▲ HIGH" if is_high else "▼ LOW "
                t_col = "bold bright_cyan" if is_high else "bold #38bdf8"
                # Normalized visual bar (-2ft to +8ft)
                norm = max(0.0, min(1.0, (ev.height_ft + 2.0) / 10.0))
                bar_len = int(round(norm * (28 if is_zoomed else 12)))
                vis = "🌊" + ("█" * bar_len)
                tide_table.add_row(
                    Text(t_icon, style=t_col),
                    Text(ev.time, style="bold white"),
                    Text(f"{ev.height_ft:+.1f} ft", style=t_col),
                    Text(vis, style="cyan" if is_high else "grey62"),
                )

        # Multi-Day Forecast Section
        fc_table = Table(
            show_header=True,
            header_style="bold #fbbf24",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        fc_table.add_column("DAY", style="bold white", width=6)
        fc_table.add_column("OUTLOOK", ratio=1)
        fc_table.add_column("HIGH / LOW", justify="right", width=14)
        fc_table.add_column("RAIN", justify="right", width=6)

        max_fc = 5 if is_zoomed else 3
        for day in w.forecast[:max_fc]:
            fc_table.add_row(
                day.day,
                f"{day.icon} {day.condition}",
                f"{day.high:.0f}{w.unit_symbol} / {day.low:.0f}{w.unit_symbol}",
                Text(f"{day.precip_prob}%", style="cyan" if day.precip_prob >= 30 else "grey62"),
            )

        return Group(
            top,
            details,
            _pane_divider(),
            tide_hdr,
            tide_table,
            _pane_divider(),
            fc_table,
        )


class TasksEmailPane(ResponsivePane):
    """Pane 4: High-Level Tasks & Priority Emails with interactive task completion."""

    BINDINGS = [
        Binding("j,down", "cursor_down", "Next Task", show=False),
        Binding("k,up", "cursor_up", "Prev Task", show=False),
        Binding("space,x,enter", "toggle_task", "Complete Task", show=True),
    ]

    DEFAULT_CSS = """
    TasksEmailPane {
        border: round #a78bfa;
        padding: 0 1;
        width: 100%;
        height: 100%;
        background: #0f172a;
    }
    TasksEmailPane:focus {
        border: double #c4b5fd;
        background: #1a1630;
    }
    """

    selected_idx: reactive[int] = reactive(0)

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = " ✅ Tasks & ✉️ Priority Inbox [Space: Check | g: Google Sync] "
        self.tasks: list[dict[str, Any]] = list(config.get("tasks", []))
        self.emails: list[dict[str, Any]] = list(config.get("emails", []))

    def reload_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self.tasks = list(tasks)
        self.selected_idx = 0
        self.refresh_view()

    def on_mount(self) -> None:
        self.refresh_view()

    def watch_selected_idx(self) -> None:
        self.refresh_view()

    def action_cursor_down(self) -> None:
        if self.tasks:
            self.selected_idx = (self.selected_idx + 1) % len(self.tasks)

    def action_cursor_up(self) -> None:
        if self.tasks:
            self.selected_idx = (self.selected_idx - 1) % len(self.tasks)

    def action_toggle_task(self) -> None:
        if not self.tasks:
            return
        task = self.tasks[self.selected_idx]
        task["done"] = not task.get("done", False)
        self.refresh_view()

    def _build_renderable(self) -> Group:
        _, h, is_zoomed = self._dims()
        open_tasks = sum(1 for t in self.tasks if not t.get("done"))
        unread_emails = sum(1 for e in self.emails if e.get("unread"))

        hdr = Text()
        hdr.append(f"Tasks ({open_tasks} open / {len(self.tasks)} total) ", style="bold #a78bfa")
        hdr.append(f"• Priority Inbox ({unread_emails} unread)", style="bold #f472b6")

        t_table = Table(show_header=is_zoomed, header_style="bold #a78bfa", box=None, padding=(0, 1), expand=True)
        t_table.add_column("", width=2)
        t_table.add_column("PRI", width=4)
        t_table.add_column("TASK / ITEM", ratio=1)
        if is_zoomed:
            t_table.add_column("PROJECT", style="cyan", width=12)
        t_table.add_column("DUE", justify="right", width=11)

        pri_colors = {"P0": "bold bright_red", "P1": "bold yellow", "P2": "cyan", "P3": "grey62"}

        max_task_rows = len(self.tasks) if is_zoomed else max(4, min(len(self.tasks), h - 9))
        for idx, t in enumerate(self.tasks[:max_task_rows]):
            is_sel = idx == self.selected_idx
            done = t.get("done", False)
            box_char = "☑" if done else "☐"
            pointer = "▸" if is_sel else " "
            pri = t.get("priority", "P2")
            title_style = "strike grey50" if done else ("bold reverse" if is_sel else "white")

            if is_zoomed:
                t_table.add_row(
                    Text(pointer, style="bold #a78bfa"),
                    Text(pri, style=pri_colors.get(pri, "white")),
                    Text(f"{box_char} {t.get('title', '')}", style=title_style),
                    str(t.get("project", "Home")),
                    Text(str(t.get("due", "")), style="grey62"),
                )
            else:
                t_table.add_row(
                    Text(pointer, style="bold #a78bfa"),
                    Text(pri, style=pri_colors.get(pri, "white")),
                    Text(f"{box_char} {t.get('title', '')}", style=title_style),
                    Text(str(t.get("due", "")), style="grey62"),
                )

        e_hdr = Text("Priority Emails & Alerts:", style="bold #f472b6")
        e_table = Table(show_header=is_zoomed, header_style="bold #f472b6", box=None, padding=(0, 1), expand=True)
        e_table.add_column("", width=2)
        e_table.add_column("FROM", width=20 if is_zoomed else 16)
        e_table.add_column("SUBJECT", ratio=1)
        if is_zoomed:
            e_table.add_column("TAG", style="cyan", width=12)
        e_table.add_column("AGE", justify="right", width=10)

        max_emails = len(self.emails) if is_zoomed else 4
        for em in self.emails[:max_emails]:
            unread = em.get("unread", False)
            dot = "●" if unread else "○"
            dot_col = "bright_magenta" if unread else "grey50"
            row_style = "bold white" if unread else "grey66"
            if is_zoomed:
                e_table.add_row(
                    Text(dot, style=dot_col),
                    Text(str(em.get("sender", "")), style=row_style),
                    Text(str(em.get("subject", "")), style=row_style),
                    str(em.get("tag", "")),
                    Text(str(em.get("time", "")), style="grey58"),
                )
            else:
                e_table.add_row(
                    Text(dot, style=dot_col),
                    Text(str(em.get("sender", ""))[:15], style=row_style),
                    Text(str(em.get("subject", "")), style=row_style),
                    Text(str(em.get("time", "")), style="grey58"),
                )

        return Group(hdr, t_table, _pane_divider(), e_hdr, e_table)


class CalendarPane(ResponsivePane):
    """Pane 5: High-Level Daily Calendar & Up-Next Timeline."""

    DEFAULT_CSS = """
    CalendarPane {
        border: round #f472b6;
        padding: 0 1;
        width: 100%;
        height: 100%;
        background: #0f172a;
    }
    CalendarPane:focus {
        border: double #f9a8d4;
        background: #231528;
    }
    """

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = " 📅 Daily Calendar & Schedule [g: Google Sync] "
        self.events: list[dict[str, Any]] = list(config.get("calendar_events", []))

    def reload_events(self, events: list[dict[str, Any]]) -> None:
        self.events = list(events)
        self.refresh_view()

    def on_mount(self) -> None:
        self.refresh_view()

    def _build_renderable(self) -> Group:
        _, h, is_zoomed = self._dims()
        up_next = next((e for e in self.events if e.get("status") == "up_next"), None)
        banner = Text()
        if up_next:
            banner.append("🔔 UP NEXT: ", style="bold bright_magenta")
            banner.append(f"{up_next.get('title')} ", style="bold white")
            banner.append(f"({up_next.get('time')} @ {up_next.get('location')})", style="bright_cyan")
        else:
            banner.append("✨ No immediate conflicts", style="bold green")

        table = Table(
            show_header=True,
            header_style="bold #f472b6",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("TIME", width=14)
        table.add_column("EVENT / RESPONSIBILITY", ratio=2)
        table.add_column("CAL", width=10)
        table.add_column("LOCATION", ratio=1, style="grey70")

        cal_colors = {
            "Work": "cyan",
            "Personal": "green",
            "Health": "yellow",
            "Family": "magenta",
            "Hockey": "bright_blue",
        }

        max_ev = len(self.events) if is_zoomed else max(6, h - 5)
        for ev in self.events[:max_ev]:
            st = ev.get("status", "upcoming")
            cal = ev.get("calendar", "Family")
            if st == "completed":
                t_style = "strike grey50"
                prefix = "✓ "
            elif st == "up_next":
                t_style = "bold bright_white"
                prefix = "▶ "
            else:
                t_style = "white"
                prefix = "  "

            loc_str = str(ev.get("location", ""))
            if not is_zoomed:
                loc_str = loc_str[:16]

            table.add_row(
                Text(str(ev.get("time", "")), style="bold #f472b6" if st == "up_next" else "grey70"),
                Text(f"{prefix}{ev.get('title', '')}", style=t_style),
                Text(cal, style=cal_colors.get(cal, "white")),
                loc_str,
            )

        return Group(banner, _pane_divider(), table)


class CommunityExtrasPane(ResponsivePane):
    """Pane 6: Daily Automation Statuses (Apps Script), Pomodoro, Git Pulse, Habits, & World Clocks."""

    BINDINGS = [
        Binding("p", "toggle_pomodoro", "Start/Pause Pomodoro", show=True),
        Binding("r", "reset_pomodoro", "Reset Timer", show=False),
        Binding("h", "cycle_habit", "Toggle Next Habit", show=True),
    ]

    DEFAULT_CSS = """
    CommunityExtrasPane {
        border: round #fb923c;
        padding: 0 1;
        width: 100%;
        height: 100%;
        background: #0f172a;
    }
    CommunityExtrasPane:focus {
        border: double #fdba74;
        background: #221915;
    }
    """

    pomo_seconds: reactive[int] = reactive(25 * 60)
    pomo_running: reactive[bool] = reactive(False)

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = " 🤖 Daily Automations, 🍅 Focus, Git & Clocks [p: Timer | h: Habit] "
        self.config = config
        self.automations: list[dict[str, Any]] = list(config.get("automations", []))
        self.habits: list[dict[str, Any]] = list(config.get("habits", []))
        self._habit_cursor = 0
        self.git_info = get_git_dev_pulse()

    def reload_automations(self, automations: list[dict[str, Any]]) -> None:
        self.automations = list(automations)
        self.refresh_view()

    def on_mount(self) -> None:
        self.refresh_view()

    def tick_second(self) -> None:
        if self.pomo_running and self.pomo_seconds > 0:
            self.pomo_seconds -= 1
        self.refresh_view()

    def action_toggle_pomodoro(self) -> None:
        self.pomo_running = not self.pomo_running
        self.refresh_view()

    def action_reset_pomodoro(self) -> None:
        self.pomo_running = False
        self.pomo_seconds = 25 * 60
        self.refresh_view()

    def action_cycle_habit(self) -> None:
        if not self.habits:
            return
        target = self.habits[self._habit_cursor % len(self.habits)]
        target["done_today"] = not target.get("done_today", False)
        if target["done_today"]:
            target["streak"] = int(target.get("streak", 0)) + 1
        else:
            target["streak"] = max(0, int(target.get("streak", 1)) - 1)
        self._habit_cursor = (self._habit_cursor + 1) % len(self.habits)
        self.refresh_view()

    def _build_renderable(self) -> Group:
        _, _, is_zoomed = self._dims()
        mins, secs = divmod(self.pomo_seconds, 60)
        pomo_state = "▶ FOCUS" if self.pomo_running else "⏸ PAUSED"
        pomo_col = "bold bright_green" if self.pomo_running else "bold yellow"

        g = self.git_info
        dirty_txt = "clean ✓" if g["dirty_count"] == 0 else f"{g['dirty_count']} modified"

        top_bar = Table.grid(padding=(0, 1), expand=True)
        top_bar.add_column(ratio=1)
        top_bar.add_column(justify="right")
        pomo_txt = Text()
        pomo_txt.append("🍅 ", style="bold #fb923c")
        pomo_txt.append(f"{mins:02d}:{secs:02d} ", style="bold bright_white")
        pomo_txt.append(f"[{pomo_state}]", style=pomo_col)

        git_txt = Text()
        git_txt.append("🐙 ", style="bold #38bdf8")
        git_txt.append(f"{g['repo']}@{g['branch']} ", style="bold white")
        git_txt.append(f"({dirty_txt})", style="green" if g["dirty_count"] == 0 else "yellow")
        top_bar.add_row(pomo_txt, git_txt)

        # Daily Automations (Google Apps Script Status Log)
        healthy_count = sum(1 for a in self.automations if "HEALTHY" in str(a.get("status", "")).upper())
        last_chk = self.automations[0].get("last_checked", "Today") if self.automations else "Today"
        auto_hdr = Text()
        auto_hdr.append(f"🤖 Daily Automations ({healthy_count}/{len(self.automations)} Healthy) ", style="bold bright_green")
        auto_hdr.append(f"• Last Run: {last_chk}", style="grey70")

        auto_table = Table(
            show_header=is_zoomed,
            header_style="bold #fb923c",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        auto_table.add_column("AUTOMATION / APPS SCRIPT", ratio=2)
        auto_table.add_column("STATUS", width=11)
        if is_zoomed:
            auto_table.add_column("RUNTIME / TZ", style="grey70", width=24)
            auto_table.add_column("VERIFIED OUTPUT", style="cyan", ratio=2)
        else:
            auto_table.add_column("INFO", justify="right", style="grey70", width=14)

        for a in self.automations:
            st = str(a.get("status", "HEALTHY")).upper()
            is_ok = "HEALTHY" in st
            badge = Text(f"● {st}", style="bold bright_green" if is_ok else "bold bright_red")
            if is_zoomed:
                auto_table.add_row(
                    Text(str(a.get("name", "")), style="bold white"),
                    badge,
                    f"{a.get('runtime', 'V8')} • {a.get('timezone', '')}",
                    str(a.get("details") or f"Updated {a.get('last_updated', '')}"),
                )
            else:
                auto_table.add_row(
                    Text(str(a.get("name", "")), style="white"),
                    badge,
                    f"{a.get('runtime', 'V8')} • {a.get('last_updated', 'OK')}",
                )

        # Habit streaks
        h_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        h_table.add_column("HABIT", ratio=1)
        h_table.add_column("STREAK", justify="right", width=10)
        max_habits = len(self.habits) if is_zoomed else 3
        for h_item in self.habits[:max_habits]:
            done = h_item.get("done_today", False)
            chk = "☑" if done else "☐"
            st_col = "bright_green" if done else "grey70"
            h_table.add_row(
                Text(f"{chk} {h_item.get('name', '')}", style=st_col),
                Text(f"🔥 {h_item.get('streak', 0)}d", style="bold #fb923c"),
            )

        # World Clocks (2x2 grid so all 4 fit cleanly and expand across full width)
        clocks = get_world_clock_strings(self.config.get("world_clocks", []))
        clock_grid = Table.grid(padding=(0, 2), expand=True)
        clock_grid.add_column(ratio=1)
        clock_grid.add_column(ratio=1)
        for idx in range(0, len(clocks), 2):
            left_lbl, left_t = clocks[idx]
            left_cell = Text(f"🌐 {left_lbl}: ", style="grey70") + Text(left_t, style="bold cyan")
            if idx + 1 < len(clocks):
                right_lbl, right_t = clocks[idx + 1]
                right_cell = Text(f"🌐 {right_lbl}: ", style="grey70") + Text(right_t, style="bold cyan")
            else:
                right_cell = Text("")
            clock_grid.add_row(left_cell, right_cell)

        return Group(
            top_bar,
            _pane_divider(),
            auto_hdr,
            auto_table,
            _pane_divider(),
            h_table,
            _pane_divider(),
            clock_grid,
        )
