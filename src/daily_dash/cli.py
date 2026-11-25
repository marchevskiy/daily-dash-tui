"""CLI entry point for launching DailyDash TUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from daily_dash import __version__
from daily_dash.app import DailyDashApp
from daily_dash.config import (
    get_default_config_path,
    load_config,
    write_sample_config,
)


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
        help="Generate a customizable starter config.yaml file and exit",
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

    if args.init_config:
        target = Path(args.config) if args.config else get_default_config_path()
        written = write_sample_config(target)
        console.print(f"[bold green]✓ Created starter configuration at:[/bold green] {written}")
        return 0

    config = load_config(args.config)

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
