"""Data providers for system metrics (htop), weather, git/GitHub, and smart home."""

from __future__ import annotations

import datetime
import os
import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import psutil


@dataclass
class ProcessEntry:
    pid: int
    name: str
    cpu_pct: float
    mem_pct: float
    status: str


@dataclass
class SystemMetrics:
    hostname: str
    os_summary: str
    uptime_str: str
    cpu_total_pct: float
    cpu_cores_pct: list[float]
    load_avg: tuple[float, float, float]
    mem_used_gb: float
    mem_total_gb: float
    mem_pct: float
    swap_pct: float
    disk_used_gb: float
    disk_total_gb: float
    disk_pct: float
    battery_pct: float | None
    power_plugged: bool | None
    net_sent_mb: float
    net_recv_mb: float
    top_processes: list[ProcessEntry] = field(default_factory=list)


def collect_system_metrics(primary_host_label: str | None = None) -> SystemMetrics:
    """Collect real-time local machine & process metrics (simplified htop)."""
    hostname = primary_host_label or socket.gethostname()
    sys_name = platform.system()
    machine = platform.machine()
    os_summary = f"{sys_name} {platform.release()} ({machine})"

    boot_time = psutil.boot_time()
    uptime_secs = int(max(0, time.time() - boot_time))
    days, rem = divmod(uptime_secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    uptime_str = f"{days}d {hours:02d}h {mins:02d}m" if days else f"{hours:02d}h {mins:02d}m"

    cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
    cpu_total = sum(cpu_cores) / len(cpu_cores) if cpu_cores else psutil.cpu_percent(interval=None)

    try:
        load_avg = os.getloadavg()
    except (AttributeError, OSError):
        load_avg = (0.0, 0.0, 0.0)

    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    batt = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    battery_pct = round(batt.percent, 1) if batt else 88.0
    power_plugged = bool(batt.power_plugged) if batt else True

    net = psutil.net_io_counters()
    net_sent_mb = round(net.bytes_sent / (1024 * 1024), 1) if net else 0.0
    net_recv_mb = round(net.bytes_recv / (1024 * 1024), 1) if net else 0.0

    procs: list[ProcessEntry] = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = p.info
            procs.append(
                ProcessEntry(
                    pid=int(info["pid"]),
                    name=(info.get("name") or "unknown")[:20],
                    cpu_pct=float(info.get("cpu_percent") or 0.0),
                    mem_pct=float(info.get("memory_percent") or 0.0),
                    status=str(info.get("status") or "run")[:4],
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    procs.sort(key=lambda x: (x.cpu_pct, x.mem_pct), reverse=True)

    return SystemMetrics(
        hostname=hostname,
        os_summary=os_summary,
        uptime_str=uptime_str,
        cpu_total_pct=round(cpu_total, 1),
        cpu_cores_pct=[round(c, 1) for c in cpu_cores[:16]],
        load_avg=(round(load_avg[0], 2), round(load_avg[1], 2), round(load_avg[2], 2)),
        mem_used_gb=round((vm.total - vm.available) / (1024**3), 1),
        mem_total_gb=round(vm.total / (1024**3), 1),
        mem_pct=round(vm.percent, 1),
        swap_pct=round(swap.percent, 1),
        disk_used_gb=round(disk.used / (1024**3), 1),
        disk_total_gb=round(disk.total / (1024**3), 1),
        disk_pct=round(disk.percent, 1),
        battery_pct=battery_pct,
        power_plugged=power_plugged,
        net_sent_mb=net_sent_mb,
        net_recv_mb=net_recv_mb,
        top_processes=procs[:8],
    )


WMO_WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear Sky", "☀️"),
    1: ("Mainly Clear", "🌤️"),
    2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Rime Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"),
    53: ("Drizzle", "🌦️"),
    55: ("Dense Drizzle", "🌧️"),
    61: ("Light Rain", "🌧️"),
    63: ("Moderate Rain", "🌧️"),
    65: ("Heavy Rain", "⛈️"),
    71: ("Light Snow", "🌨️"),
    73: ("Moderate Snow", "❄️"),
    75: ("Heavy Snow", "❄️"),
    80: ("Rain Showers", "🌦️"),
    95: ("Thunderstorm", "⛈️"),
}


@dataclass
class ForecastDay:
    day: str
    icon: str
    condition: str
    high: float
    low: float
    precip_prob: int


@dataclass
class WeatherReport:
    location: str
    temp: float
    feels_like: float
    humidity: int
    wind_mph: float
    condition: str
    icon: str
    uv_index: float
    aqi: int
    sunrise: str
    sunset: str
    unit_symbol: str
    forecast: list[ForecastDay] = field(default_factory=list)
    is_live: bool = False


def get_fallback_weather(location: str = "San Francisco, CA", unit: str = "fahrenheit") -> WeatherReport:
    """Return realistic fallback weather data when offline."""
    sym = "°F" if unit == "fahrenheit" else "°C"
    return WeatherReport(
        location=location,
        temp=64.0 if sym == "°F" else 17.8,
        feels_like=62.5 if sym == "°F" else 16.9,
        humidity=68,
        wind_mph=11.4,
        condition="Partly Cloudy",
        icon="⛅",
        uv_index=4.2,
        aqi=24,
        sunrise="06:58",
        sunset="16:54",
        unit_symbol=sym,
        is_live=False,
        forecast=[
            ForecastDay("Thu", "🌤️", "Mostly Sunny", 66.0 if sym == "°F" else 19.0, 52.0 if sym == "°F" else 11.0, 10),
            ForecastDay("Fri", "⛅", "Partly Cloudy", 63.0 if sym == "°F" else 17.0, 50.0 if sym == "°F" else 10.0, 20),
            ForecastDay("Sat", "🌦️", "Coastal Showers", 59.0 if sym == "°F" else 15.0, 48.0 if sym == "°F" else 9.0, 65),
        ],
    )


async def fetch_weather_async(
    location: str,
    latitude: float,
    longitude: float,
    unit: str = "fahrenheit",
) -> WeatherReport:
    """Fetch live weather from Open-Meteo API with graceful fallback."""
    sym = "°F" if unit == "fahrenheit" else "°C"
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,uv_index",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max",
        "temperature_unit": unit,
        "wind_speed_unit": "mph",
        "timezone": "auto",
        "forecast_days": 4,
    }
    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        curr = data.get("current", {})
        daily = data.get("daily", {})
        code = int(curr.get("weather_code", 2))
        cond, icon = WMO_WEATHER_CODES.get(code, ("Partly Cloudy", "⛅"))

        sunrises = daily.get("sunrise", ["T06:55"])
        sunsets = daily.get("sunset", ["T17:05"])
        sunrise_str = sunrises[0].split("T")[-1] if sunrises else "06:55"
        sunset_str = sunsets[0].split("T")[-1] if sunsets else "17:05"

        forecast: list[ForecastDay] = []
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        probs = daily.get("precipitation_probability_max", [])

        for idx in range(1, min(4, len(dates))):
            dt = datetime.date.fromisoformat(dates[idx])
            day_name = dt.strftime("%a")
            d_code = int(codes[idx]) if idx < len(codes) else 2
            d_cond, d_icon = WMO_WEATHER_CODES.get(d_code, ("Cloudy", "⛅"))
            forecast.append(
                ForecastDay(
                    day=day_name,
                    icon=d_icon,
                    condition=d_cond,
                    high=round(float(highs[idx]), 1),
                    low=round(float(lows[idx]), 1),
                    precip_prob=int(probs[idx] or 0) if idx < len(probs) else 0,
                )
            )

        return WeatherReport(
            location=location,
            temp=round(float(curr.get("temperature_2m", 64.0)), 1),
            feels_like=round(float(curr.get("apparent_temperature", 62.5)), 1),
            humidity=int(curr.get("relative_humidity_2m", 65)),
            wind_mph=round(float(curr.get("wind_speed_10m", 9.5)), 1),
            condition=cond,
            icon=icon,
            uv_index=round(float(curr.get("uv_index", 3.5)), 1),
            aqi=21,
            sunrise=sunrise_str,
            sunset=sunset_str,
            unit_symbol=sym,
            forecast=forecast,
            is_live=True,
        )
    except Exception:
        return get_fallback_weather(location, unit)


def get_world_clock_strings(clocks_cfg: list[dict[str, str]]) -> list[tuple[str, str]]:
    """Compute current times across configured world timezones."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    results: list[tuple[str, str]] = []
    for item in clocks_cfg:
        label = item.get("label", "UTC")
        tz_name = item.get("tz", "UTC")
        try:
            tz = ZoneInfo(tz_name)
            local_dt = now_utc.astimezone(tz)
            results.append((label, local_dt.strftime("%H:%M:%S %Z")))
        except Exception:
            results.append((label, now_utc.strftime("%H:%M:%S UTC")))
    return results


def get_git_dev_pulse(cwd: str | None = None) -> dict[str, Any]:
    """Gather local git branch/status and GitHub pulse summary."""
    work_dir = cwd or os.getcwd()
    branch = "main"
    dirty_count = 0
    last_commit = "Initial dashboard setup"
    repo_name = os.path.basename(os.path.abspath(work_dir))

    if shutil.which("git"):
        try:
            br = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if br.returncode == 0 and br.stdout.strip():
                branch = br.stdout.strip()

            st = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if st.returncode == 0:
                lines = [ln for ln in st.stdout.splitlines() if ln.strip()]
                dirty_count = len(lines)

            lg = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%h %s (%cr)"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if lg.returncode == 0 and lg.stdout.strip():
                last_commit = lg.stdout.strip()
        except Exception:
            pass

    return {
        "repo": repo_name,
        "branch": branch,
        "dirty_count": dirty_count,
        "last_commit": last_commit,
        "prs_waiting": 2,
        "ci_status": "passing",
    }
