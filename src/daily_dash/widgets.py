"""Textual pane widgets for DailyDash TUI."""

from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
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


def _render_bar(pct: float, width: int = 16) -> Text:
    """Render an htop-style color-coded progress bar."""
    clamped = max(0.0, min(100.0, pct))
    filled = int(round((clamped / 100.0) * width))
    empty = max(0, width - filled)
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


class SystemMonitorPane(Static, can_focus=True):
    """Pane 1: Simplified htop & MacBook / Managed Fleet Monitor."""

    DEFAULT_CSS = """
    SystemMonitorPane {
        border: round #38bdf8;
        padding: 0 1;
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
            self.config.get("profile", {}).get("primary_host")
        )
        self.update(self._build_renderable())

    def on_mount(self) -> None:
        self.refresh_metrics()

    def _build_renderable(self) -> Group:
        m = self.metrics
        header = Text()
        header.append(f"Host: {m.hostname} ", style="bold cyan")
        header.append(f"• Up {m.uptime_str} ", style="grey70")
        batt_icon = "⚡" if m.power_plugged else "🔋"
        header.append(f"• {batt_icon} {m.battery_pct:.0f}%", style="bold green")

        gauges = Table.grid(padding=(0, 1))
        gauges.add_column(style="bold white", width=7)
        gauges.add_column()
        gauges.add_column(style="dim", justify="right")

        gauges.add_row("CPU", _render_bar(m.cpu_total_pct, 14), f"Load {m.load_avg[0]:.2f}")
        gauges.add_row(
            "MEM",
            _render_bar(m.mem_pct, 14),
            f"{m.mem_used_gb}/{m.mem_total_gb}G",
        )
        gauges.add_row(
            "DSK",
            _render_bar(m.disk_pct, 14),
            f"{m.disk_used_gb:.0f}/{m.disk_total_gb:.0f}G",
        )

        # Per-core mini spark strip
        core_line = Text("Cores: ", style="dim")
        blocks = " ▂▃▄▅▆▇█"
        for c in m.cpu_cores_pct[:12]:
            idx = min(len(blocks) - 1, int((c / 100.0) * (len(blocks) - 1)))
            col = "green" if c < 60 else ("yellow" if c < 85 else "red")
            core_line.append(blocks[idx], style=f"bold {col}")
        core_line.append(f"  Net ↑{m.net_sent_mb:.0f}M ↓{m.net_recv_mb:.0f}M", style="grey70")

        # Top processes table
        proc_table = Table(
            show_header=True,
            header_style="bold #38bdf8",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        proc_table.add_column("PID", style="dim", width=6)
        proc_table.add_column("PROCESS", style="white", ratio=1)
        proc_table.add_column("CPU%", justify="right", width=6)
        proc_table.add_column("MEM%", justify="right", width=6)

        for p in m.top_processes[:5]:
            c_style = "bold red" if p.cpu_pct > 50 else ("yellow" if p.cpu_pct > 15 else "green")
            proc_table.add_row(
                str(p.pid),
                p.name,
                Text(f"{p.cpu_pct:4.1f}", style=c_style),
                f"{p.mem_pct:4.1f}",
            )

        # Managed Fleet quick strip
        fleet_line = Text("Fleet: ", style="bold #38bdf8")
        for host in self.config.get("managed_hosts", [])[1:]:
            h_name = host.get("hostname", "").split(".")[0]
            h_cpu = host.get("cpu_pct", 0.0)
            fleet_line.append(f"● {h_name} ", style="green")
            fleet_line.append(f"({h_cpu:.0f}% CPU)  ", style="grey70")

        return Group(header, gauges, core_line, Text("─" * 38, style="grey23"), proc_table, fleet_line)


class SmartHomePane(Static, can_focus=True):
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
        self.border_title = " 🏠 Google Home & Devices [Space: Toggle | s: Scan LAN] "
        self.devices: list[dict[str, Any]] = list(config.get("google_home_devices", []))

    def reload_devices(self, devices: list[dict[str, Any]]) -> None:
        self.devices = list(devices)
        self.selected_idx = 0
        self.update(self._build_renderable())

    def on_mount(self) -> None:
        self.update(self._build_renderable())

    def watch_selected_idx(self) -> None:
        self.update(self._build_renderable())

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
            dev["state"] = "On • 85% Warm White" if dev["active"] else "Off • Standby"
        elif dtype == "lock":
            dev["state"] = "Locked • Battery 92%" if dev["active"] else "Unlocked • Manual"
        elif dtype == "speaker":
            dev["state"] = "Playing • Lo-Fi Beats" if dev["active"] else "Idle • Ready to Cast"
        elif dtype == "thermostat":
            dev["state"] = "Heating • 70°F → 72°F" if dev["active"] else "Eco Mode • 65°F"
        else:
            dev["state"] = "Active • Auto" if dev["active"] else "Off • Standby"
        self.update(self._build_renderable())

    def _build_renderable(self) -> Group:
        active_count = sum(1 for d in self.devices if d.get("active"))
        summary = Text()
        summary.append("Home Hub: ", style="bold #34d399")
        summary.append(f"{len(self.devices)} online • {active_count} active ", style="white")
        summary.append("• Nest Wifi: 610 Mbps", style="grey70")

        table = Table(
            show_header=True,
            header_style="bold #34d399",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("", width=2)
        table.add_column("DEVICE", ratio=1)
        table.add_column("ROOM", style="grey70", width=12)
        table.add_column("STATE", ratio=1)

        icons = {
            "thermostat": "🌡️",
            "light": "💡",
            "speaker": "🔊",
            "lock": "🔒",
            "air": "🍃",
        }

        for idx, dev in enumerate(self.devices):
            is_sel = idx == self.selected_idx
            pointer = "▸" if is_sel else " "
            icon = icons.get(dev.get("type", ""), "📟")
            active = dev.get("active", False)
            dot_style = "bold bright_green" if active else "grey50"
            name_style = "bold reverse" if is_sel else ("bold white" if active else "grey62")
            state_style = "bright_green" if active else "grey58"

            table.add_row(
                Text(pointer, style="bold #34d399"),
                Text(f"{icon} {dev.get('name', 'Device')}", style=name_style),
                str(dev.get("room", "")),
                Text(f"● {dev.get('state', '')}", style=state_style if active else dot_style),
            )

        footer = Text("Use ↑/↓ (or j/k) and Space to control Google Home devices", style="italic grey50")
        return Group(summary, Text("─" * 38, style="grey23"), table, footer)


class WeatherPane(Static, can_focus=True):
    """Pane 3: Live Weather & 3-Day Forecast."""

    DEFAULT_CSS = """
    WeatherPane {
        border: round #fbbf24;
        padding: 0 1;
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
        self.border_title = " 🌦️ Weather & Environment "
        prof = config.get("profile", {})
        self.report: WeatherReport = get_fallback_weather(
            prof.get("location", "San Francisco, CA"),
            prof.get("temperature_unit", "fahrenheit"),
        )

    def update_weather(self, report: WeatherReport) -> None:
        self.report = report
        self.update(self._build_renderable())

    def on_mount(self) -> None:
        self.update(self._build_renderable())

    def _build_renderable(self) -> Group:
        w = self.report
        badge = "LIVE" if w.is_live else "CACHED"
        badge_style = "bold bright_green" if w.is_live else "bold yellow"

        top = Text()
        top.append(f"{w.icon}  {w.temp:.1f}{w.unit_symbol} ", style="bold bright_yellow")
        top.append(f"{w.condition} ", style="bold white")
        top.append(f"[{badge}]", style=badge_style)

        loc_line = Text(f"📍 {w.location}  •  Feels like {w.feels_like:.1f}{w.unit_symbol}", style="grey78")

        details = Table.grid(padding=(0, 2))
        details.add_column()
        details.add_column()
        details.add_row(
            Text(f"💧 Humidity: {w.humidity}%", style="cyan"),
            Text(f"💨 Wind: {w.wind_mph:.1f} mph", style="cyan"),
        )
        details.add_row(
            Text(f"☀️ UV Index: {w.uv_index}", style="yellow"),
            Text(f"🍃 AQI: {w.aqi} (Good)", style="green"),
        )
        details.add_row(
            Text(f"🌅 Sunrise: {w.sunrise}", style="grey70"),
            Text(f"🌇 Sunset: {w.sunset}", style="grey70"),
        )

        fc_table = Table(
            show_header=True,
            header_style="bold #fbbf24",
            box=None,
            padding=(0, 1),
            expand=True,
        )
        fc_table.add_column("DAY", style="bold white", width=5)
        fc_table.add_column("OUTLOOK", ratio=1)
        fc_table.add_column("HIGH / LOW", justify="right", width=13)
        fc_table.add_column("RAIN", justify="right", width=6)

        for day in w.forecast:
            fc_table.add_row(
                day.day,
                f"{day.icon} {day.condition}",
                f"{day.high:.0f}{w.unit_symbol} / {day.low:.0f}{w.unit_symbol}",
                Text(f"{day.precip_prob}%", style="cyan" if day.precip_prob >= 30 else "grey62"),
            )

        return Group(top, loc_line, details, Text("─" * 38, style="grey23"), fc_table)


class TasksEmailPane(Static, can_focus=True):
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
        self.update(self._build_renderable())

    def on_mount(self) -> None:
        self.update(self._build_renderable())

    def watch_selected_idx(self) -> None:
        self.update(self._build_renderable())

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
        self.update(self._build_renderable())

    def _build_renderable(self) -> Group:
        open_tasks = sum(1 for t in self.tasks if not t.get("done"))
        unread_emails = sum(1 for e in self.emails if e.get("unread"))

        hdr = Text()
        hdr.append(f"Tasks ({open_tasks} open) ", style="bold #a78bfa")
        hdr.append(f"• Inbox ({unread_emails} unread)", style="bold #f472b6")

        t_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        t_table.add_column("", width=2)
        t_table.add_column("PRI", width=4)
        t_table.add_column("TASK", ratio=1)
        t_table.add_column("DUE", justify="right", width=11)

        pri_colors = {"P0": "bold bright_red", "P1": "bold yellow", "P2": "cyan", "P3": "grey62"}

        for idx, t in enumerate(self.tasks):
            is_sel = idx == self.selected_idx
            done = t.get("done", False)
            box_char = "☑" if done else "☐"
            pointer = "▸" if is_sel else " "
            pri = t.get("priority", "P2")
            title_style = "strike grey50" if done else ("bold reverse" if is_sel else "white")

            t_table.add_row(
                Text(pointer, style="bold #a78bfa"),
                Text(pri, style=pri_colors.get(pri, "white")),
                Text(f"{box_char} {t.get('title', '')}", style=title_style),
                Text(str(t.get("due", "")), style="grey62"),
            )

        e_hdr = Text("Priority Emails:", style="bold #f472b6")
        e_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        e_table.add_column("", width=2)
        e_table.add_column("FROM", width=16)
        e_table.add_column("SUBJECT", ratio=1)
        e_table.add_column("AGE", justify="right", width=9)

        for em in self.emails[:4]:
            unread = em.get("unread", False)
            dot = "●" if unread else "○"
            dot_col = "bright_magenta" if unread else "grey50"
            row_style = "bold white" if unread else "grey66"
            e_table.add_row(
                Text(dot, style=dot_col),
                Text(str(em.get("sender", ""))[:15], style=row_style),
                Text(str(em.get("subject", "")), style=row_style),
                Text(str(em.get("time", "")), style="grey58"),
            )

        return Group(hdr, t_table, Text("─" * 38, style="grey23"), e_hdr, e_table)


class CalendarPane(Static, can_focus=True):
    """Pane 5: High-Level Daily Calendar & Up-Next Timeline."""

    DEFAULT_CSS = """
    CalendarPane {
        border: round #f472b6;
        padding: 0 1;
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
        self.update(self._build_renderable())

    def on_mount(self) -> None:
        self.update(self._build_renderable())

    def _build_renderable(self) -> Group:
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
        table.add_column("TIME", width=13)
        table.add_column("EVENT", ratio=1)
        table.add_column("CAL", width=8)
        table.add_column("LOC", width=13, style="grey70")

        cal_colors = {
            "Work": "cyan",
            "Personal": "green",
            "Health": "yellow",
            "Family": "magenta",
        }

        for ev in self.events:
            st = ev.get("status", "upcoming")
            cal = ev.get("calendar", "Work")
            if st == "completed":
                t_style = "strike grey50"
                prefix = "✓ "
            elif st == "up_next":
                t_style = "bold bright_white"
                prefix = "▶ "
            else:
                t_style = "white"
                prefix = "  "

            table.add_row(
                Text(str(ev.get("time", "")), style="bold #f472b6" if st == "up_next" else "grey70"),
                Text(f"{prefix}{ev.get('title', '')}", style=t_style),
                Text(cal, style=cal_colors.get(cal, "white")),
                str(ev.get("location", ""))[:13],
            )

        return Group(banner, Text("─" * 38, style="grey23"), table)


class CommunityExtrasPane(Static, can_focus=True):
    """Pane 6: Community-Favorite TUI Widgets (Pomodoro, Habits, Git/GitHub Pulse, World Clocks)."""

    BINDINGS = [
        Binding("p", "toggle_pomodoro", "Start/Pause Pomodoro", show=True),
        Binding("r", "reset_pomodoro", "Reset Timer", show=False),
        Binding("h", "cycle_habit", "Toggle Next Habit", show=True),
    ]

    DEFAULT_CSS = """
    CommunityExtrasPane {
        border: round #fb923c;
        padding: 0 1;
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
        self.border_title = " 🚀 Focus, Git Pulse, Habits & World Clocks [p: Timer | h: Habit] "
        self.config = config
        self.habits: list[dict[str, Any]] = list(config.get("habits", []))
        self._habit_cursor = 0
        self.git_info = get_git_dev_pulse()

    def on_mount(self) -> None:
        self.update(self._build_renderable())

    def tick_second(self) -> None:
        if self.pomo_running and self.pomo_seconds > 0:
            self.pomo_seconds -= 1
        self.update(self._build_renderable())

    def action_toggle_pomodoro(self) -> None:
        self.pomo_running = not self.pomo_running
        self.update(self._build_renderable())

    def action_reset_pomodoro(self) -> None:
        self.pomo_running = False
        self.pomo_seconds = 25 * 60
        self.update(self._build_renderable())

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
        self.update(self._build_renderable())

    def _build_renderable(self) -> Group:
        mins, secs = divmod(self.pomo_seconds, 60)
        pomo_state = "▶ FOCUS" if self.pomo_running else "⏸ PAUSED"
        pomo_col = "bold bright_green" if self.pomo_running else "bold yellow"

        pomo_line = Text()
        pomo_line.append("🍅 Pomodoro: ", style="bold #fb923c")
        pomo_line.append(f"{mins:02d}:{secs:02d} ", style="bold bright_white")
        pomo_line.append(f"[{pomo_state}]", style=pomo_col)

        # Git / GitHub pulse
        g = self.git_info
        git_line = Text()
        git_line.append("🐙 Git Pulse: ", style="bold #38bdf8")
        git_line.append(f"{g['repo']}@{g['branch']} ", style="bold white")
        dirty_txt = "clean ✓" if g["dirty_count"] == 0 else f"{g['dirty_count']} modified"
        git_line.append(f"({dirty_txt}) • CI: {g['ci_status']}", style="green" if g["dirty_count"] == 0 else "yellow")

        # Habit streaks
        h_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        h_table.add_column("HABIT", ratio=1)
        h_table.add_column("STREAK", justify="right", width=11)
        for h in self.habits:
            done = h.get("done_today", False)
            chk = "☑" if done else "☐"
            st = "bright_green" if done else "grey70"
            h_table.add_row(
                Text(f"{chk} {h.get('name', '')}", style=st),
                Text(f"🔥 {h.get('streak', 0)}d", style="bold #fb923c"),
            )

        # World Clocks
        clocks = get_world_clock_strings(self.config.get("world_clocks", []))
        clock_table = Table.grid(padding=(0, 2), expand=True)
        clock_table.add_column(style="grey70")
        clock_table.add_column(justify="right", style="bold cyan")
        for label, t_str in clocks[:3]:
            clock_table.add_row(f"🌐 {label}", t_str)

        return Group(
            pomo_line,
            git_line,
            Text("─" * 38, style="grey23"),
            h_table,
            Text("─" * 38, style="grey23"),
            clock_table,
        )
