"""CLI entry point for launching, syncing, scanning, and configuring DailyDash TUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from daily_dash import __version__
from daily_dash.app import DailyDashApp
from daily_dash.config import (
    get_default_config_path,
    load_config,
    merge_discovered_devices,
    save_config,
    write_sample_config,
)
from daily_dash.discovery import scan_network
from daily_dash.google_sync import sync_config_with_google


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dailydash",
        description="Launch your customized multi-pane terminal TUI dashboard for daily life.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"dailydash {__version__}",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to custom config.yaml (default: ~/.config/daily-dash/config.yaml)",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Generate your personalized config.yaml (auto-syncs Google Workspace if available) and exit",
    )
    parser.add_argument(
        "--sync-google",
        action="store_true",
        help="Pull live Google Calendar events and Google Docs tasks into config.yaml and exit",
    )
    parser.add_argument(
        "--scan-network",
        action="store_true",
        help="Scan local LAN (mDNS/Bonjour, ARP, Google Cast :8008/:8009, Matter :5540, SSH :22) and update config.yaml",
    )
    parser.add_argument(
        "--subnet",
        type=str,
        default=None,
        help="Optional IPv4 CIDR subnet to scan with --scan-network (e.g., 192.168.86.0/24)",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Run the interactive CLI setup wizard to customize your hosts, devices, and Google Workspace sync",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run with cached/local providers without making network calls",
    )
    parser.add_argument(
        "--export-svg",
        type=str,
        default=None,
        metavar="PATH",
        help="Render the dashboard headlessly and export an SVG snapshot to PATH",
    )
    return parser


def _print_scan_results(console: Console, result: dict[str, Any]) -> None:
    console.print(
        f"[bold cyan]🔍 Scanned Subnet:[/bold cyan] {result['subnet']} "
        f"(Local IP: [bold]{result['local_ip']}[/bold])"
    )

    gh_devs = result.get("google_home_devices", [])
    hosts = result.get("managed_hosts", [])

    table = Table(title="Discovered LAN Hosts & Smart Home Devices", show_lines=False)
    table.add_column("Category", style="bold cyan")
    table.add_column("Name / Hostname", style="bold white")
    table.add_column("IP / Location", style="green")
    table.add_column("Details", style="grey78")

    for h in hosts:
        table.add_row("💻 Managed Host", str(h.get("hostname")), str(h.get("ip", "")), str(h.get("role", "")))

    for d in gh_devs:
        table.add_row("🏠 Smart Device", str(d.get("name")), str(d.get("room", "")), str(d.get("state", "")))

    console.print(table)


def _run_interactive_wizard(console: Console, config: dict[str, Any], target_path: Path) -> Path:
    console.print(
        Panel.fit(
            "[bold cyan]DailyDash TUI — Interactive Configuration Wizard[/bold cyan]\n"
            "Customize your profile, scan your LAN for Google Home & MacBook hosts, and sync Google Workspace.",
            border_style="cyan",
        )
    )

    prof = config.setdefault("profile", {})
    prof["name"] = Prompt.ask("Your Name", default=str(prof.get("name", "Alex")))
    prof["primary_host"] = Prompt.ask(
        "Primary MacBook / Workstation Hostname",
        default=str(prof.get("primary_host", "Alex-MacBook-Pro.local")),
    )
    prof["location"] = Prompt.ask(
        "Weather Location Label",
        default=str(prof.get("location", "San Francisco, CA")),
    )
    prof["temperature_unit"] = Prompt.ask(
        "Temperature Unit",
        choices=["fahrenheit", "celsius"],
        default=str(prof.get("temperature_unit", "fahrenheit")),
    )

    if Confirm.ask("Scan your local network (LAN / mDNS / Google Cast / Matter) for devices now?", default=True):
        res = scan_network(auth_cfg=config.get("smart_home_auth"))
        _print_scan_results(console, res)
        config["google_home_devices"] = merge_discovered_devices(
            config.get("google_home_devices", []),
            res.get("google_home_devices", []),
        )
        if res.get("managed_hosts"):
            config["managed_hosts"] = list(res["managed_hosts"])[:6]

    if Confirm.ask("Sync live events & tasks from connected Google Calendar & Google Docs now?", default=True):
        sync_config_with_google(config)
        console.print(
            f"[green]✓ Synced {len(config.get('calendar_events', []))} calendar events "
            f"and {len(config.get('tasks', []))} tasks from Google Workspace.[/green]"
        )

    saved = save_config(config, target_path)
    console.print(f"[bold green]✓ Saved personalized configuration to:[/bold green] {saved}")
    return saved


def _export_svg_snapshot(config: dict, output_path: str, offline: bool = False) -> None:
    import asyncio

    async def _capture() -> None:
        app = DailyDashApp(config=config, offline=offline)
        async with app.run_test(size=(150, 44)) as pilot:
            await pilot.pause(0.4)
            app.save_screenshot(filename=Path(output_path).name, path=str(Path(output_path).parent))

    asyncio.run(_capture())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console()
    target_path = Path(args.config) if args.config else get_default_config_path()

    if args.init_config:
        written = write_sample_config(
            target_path,
            sync_google=not args.offline,
            scan_lan=args.scan_network,
            subnet=args.subnet,
        )
        console.print(f"[bold green]✓ Generated personalized config at:[/bold green] {written}")
        return 0

    config = load_config(target_path)

    if args.configure:
        _run_interactive_wizard(console, config, target_path)
        return 0

    if args.scan_network:
        res = scan_network(subnet=args.subnet, auth_cfg=config.get("smart_home_auth"))
        _print_scan_results(console, res)
        config["google_home_devices"] = merge_discovered_devices(
            config.get("google_home_devices", []),
            res.get("google_home_devices", []),
        )
        if res.get("managed_hosts"):
            config["managed_hosts"] = list(res["managed_hosts"])[:6]
        saved = save_config(config, target_path)
        console.print(f"[bold green]✓ Updated config with discovered LAN devices at:[/bold green] {saved}")
        if not args.sync_google and not args.export_svg:
            return 0

    if args.sync_google:
        sync_config_with_google(config)
        saved = save_config(config, target_path)
        console.print(
            f"[bold green]✓ Synced Google Calendar ({len(config.get('calendar_events', []))} events) "
            f"& Google Docs ({len(config.get('tasks', []))} tasks) to:[/bold green] {saved}"
        )
        if not args.export_svg:
            return 0

    if args.export_svg:
        out = Path(args.export_svg).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        _export_svg_snapshot(config, str(out), offline=args.offline)
        console.print(f"[bold cyan]✓ Exported dashboard SVG snapshot to:[/bold cyan] {out}")
        return 0

    app = DailyDashApp(config=config, offline=args.offline)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
