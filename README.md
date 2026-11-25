# DailyDash TUI (`dailydash`)

A customizable, multi-pane terminal user interface (TUI) dashboard for your daily life, built with [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich).

![DailyDash TUI Snapshot](assets/dashboard-preview.svg)

## ✨ Key Panes & Features

DailyDash organizes your daily operational & personal life into **6 distinct, keyboard-navigable panes**:

1. **`[1]` 💻 MacBook & Fleet Monitor (Simplified `htop`)**
   - Live CPU, Memory, Disk gauges, per-core sparklines, battery/power status, network I/O counters, and top resource-consuming processes (`psutil`).
   - Quick status strip for other machines you manage on your LAN (e.g., `MacBook-Pro-M3.local`, `homelab-nas.local`, `pi-pihole.local`).
2. **`[2]` 🏠 Google Home & Smart Devices**
   - Status and interactive control (`Space` / `Enter` to toggle, `j`/`k` or `↑`/`↓` to select) for Google Home / Nest / Matter devices (Nest Thermostat, Smart Lights, Nest Hub Max speaker, Nest × Yale Lock, Air Purifier).
3. **`[3]` 🌦️ Weather & Environment**
   - Live local weather powered by Open-Meteo (with automatic offline fallback), feels-like temperature, humidity, wind speed, UV index, AQI, sunrise/sunset times, and a 3-day outlook.
4. **`[4]` ✅ Tasks & ✉️ Priority Inbox**
   - High-level view of your daily prioritized tasks (`P0`–`P3`) with interactive completion toggling (`Space` / `x`), paired with an unread Priority Email summary across Work, GitHub, and Home alerts.
5. **`[5]` 📅 Daily Calendar & Schedule**
   - Up-Next meeting callout banner with time and location/link, plus a color-coded chronological timeline across Work, Personal, Health, and Family calendars.
6. **`[6]` 🚀 Focus, Git Pulse, Habits & World Clocks *(Community Favorites)***
   - Inspired by popular open-source TUI dashboards (`wtfutil`, `sampler`, `gh-dash`, `tiny-care-terminal`):
     - **Pomodoro Focus Timer**: Interactive 25-minute countdown (`p` to start/pause, `r` to reset).
     - **Git & GitHub Pulse**: Live local repo branch, dirty file counter, and CI status at a glance.
     - **Daily Habit Streaks**: Track daily habits with streak counters (`h` to toggle).
     - **World Clocks**: Live multi-timezone clock strip (Local/SF, New York, UTC, Tokyo).

---

## 🚀 Quick Start (CLI)

### 1. Install

```bash
git clone https://github.com/marchevskiy/daily-dash-tui.git
cd daily-dash-tui
pip install -e .
```

### 2. Launch from the CLI

```bash
dailydash
# or
daily-dash
```

### 3. CLI Options

```bash
# Generate a starter YAML config at ~/.config/daily-dash/config.yaml
dailydash --init-config

# Launch with a custom config file
dailydash --config /path/to/config.yaml

# Launch in offline mode (uses local/cached data without network calls)
dailydash --offline

# Export an SVG screenshot of your dashboard
dailydash --export-svg assets/dashboard-preview.svg
```

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `1` – `6` | Jump focus directly to Pane `1` through `6` |
| `Tab` / `Shift+Tab` | Cycle focus across panes |
| `z` | **Zoom / Maximize** currently focused pane (press `z` again to restore grid) |
| `j` / `k` or `↑` / `↓` | Move cursor inside **Google Home** or **Tasks** panes |
| `Space` / `Enter` | Toggle selected Google Home device (Pane 2) or check/uncheck Task (Pane 4) |
| `p` | Start / Pause Pomodoro timer (when Pane 6 is focused) |
| `h` | Toggle next daily habit streak (when Pane 6 is focused) |
| `r` | Refresh all metrics and live weather immediately |
| `q` | Quit dashboard |

---

## ⚙️ Configuration

Run `dailydash --init-config` to create `~/.config/daily-dash/config.yaml`. You can customize:
- **`profile`**: Name, primary MacBook hostname, city, latitude/longitude, and temperature unit (`fahrenheit` or `celsius`).
- **`managed_hosts`**: Your MacBook and other servers/Raspberry Pis on your network.
- **`google_home_devices`**: Your rooms and smart devices.
- **`tasks`**, **`emails`**, **`calendar_events`**, **`habits`**, and **`world_clocks`**.
