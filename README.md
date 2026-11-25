# DailyDash TUI (`dailydash`)

A customizable, multi-pane terminal user interface (TUI) dashboard for your daily life, built with [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich).

![DailyDash TUI Snapshot](assets/dashboard-preview.svg)

## ✨ Key Panes & Features

DailyDash organizes your daily operational & personal life into **6 distinct, keyboard-navigable panes**:

1. **`[1]` 💻 MacBook & Fleet Monitor (Simplified `htop`)**
   - Live CPU, Memory, Disk gauges, per-core sparklines, battery/power status, network I/O counters, and top resource-consuming processes (`psutil`).
   - Quick status strip for your MacBook and any discovered LAN machines (`Alex-MacBook-Pro.local`, `nest-wifi-pro-gateway.local`, `poe-nvr-cameras.local`).
2. **`[2]` 🏠 Google Home & SF Smart Devices (with Local Network Auto-Discovery)**
   - Pre-configured for your 1950s SF Rowhouse setup (Upstairs/Downstairs Nest Thermostat + remote sensor, Nest Protect Smoke/CO & Garage Rate-of-Rise Heat Detector, Front Tunnel & Yard Smart Deadbolts, Wi-Fi Garage Opener & Lintel Floodlight Cam, 5-Zone Wi-Fi Water Leak Sensors, 2700K Warm White LEDs & Lutron Shades).
   - **Auto-Discovery (`--scan-network` or press `s` inside the TUI)**: Automatically scans your local LAN via **mDNS/Bonjour** (`dns-sd` on macOS / `avahi-browse` on Linux), **ARP neighbor table** (`arp -a` / `ip neigh`), and concurrent TCP probes for **Google Cast / Nest** (`:8008` `/setup/eureka_info`, `:8009`, `:8443`), **Matter** (`:5540`), and **macOS/SSH hosts** (`:22`, `:548`, `:5900`).
3. **`[3]` 🌦️ Weather & Environment**
   - Live San Francisco weather powered by Open-Meteo (with automatic offline fallback), feels-like temperature, humidity, wind speed, UV index, AQI, sunrise/sunset times (critical for walking Kosmo before dark!), and a 3-day outlook.
4. **`[4]` ✅ Tasks & ✉️ Priority Inbox (Live Google Docs Sync)**
   - Syncs directly with your **Shared Shopping List & Weekly Tasks** Google Doc and **1950s SF Home Maintenance Strategy** checklist (`--sync-google` or press `g` inside the TUI).
   - Interactive completion toggling (`Space` / `x`), paired with an unread Priority Inbox & Apps Script Automation status summary.
5. **`[5]` 📅 Daily Calendar & Schedule (Live Google Calendar Sync)**
   - Syncs directly with your Google Calendars (`mjalexja@gmail.com`, `amarchev91@gmail.com`, `marchevskiy@google.com`, and Hockey calendars `Silver Squids` / `Flying Squids`).
   - Shows an **Up-Next** banner plus your daily responsibility timeline (`[Alex]` / `[MJ]` Leo wake-up, daycare drop-off/pick-up at Villa de Kapuso YMCA, Kosmo walks before sunset, dinner, bath & bedtime).
6. **`[6]` 🚀 Focus, Git Pulse, Habits & World Clocks *(Community Favorites)***
   - **Pomodoro Focus Timer**: Interactive 25-minute countdown (`p` to start/pause, `r` to reset).
   - **Git & GitHub Pulse**: Live local repo branch, dirty file counter, and CI status at a glance.
   - **Daily Habit Streaks**: Track daily habits (e.g., walking Kosmo before 4:54 PM sunset, Leo pickup `<8h`, ground-floor humidity 40–55%) with streak counters (`h` to toggle).
   - **World Clocks**: Live multi-timezone clock strip (SF/Sunnyvale, Chicago Bulls/Blackhawks, New York, London Arsenal FC).

---

## 🚀 Quick Start (CLI)

### 1. Install

```bash
git clone https://github.com/marchevskiy/daily-dash-tui.git
cd daily-dash-tui
pip install -e .
```

### 2. Personalize & Auto-Discover Your Config

```bash
# Generate ~/.config/daily-dash/config.yaml synced with your Google Calendar/Docs & LAN scan
dailydash --init-config --scan-network

# Or run the interactive CLI configuration wizard
dailydash --configure

# Pull latest events & tasks from Google Calendar & Google Docs anytime
dailydash --sync-google

# Scan your local Wi-Fi subnet for Google Home / Cast / Matter devices & MacBooks
dailydash --scan-network
```

### 3. Launch from the CLI

```bash
dailydash
# or
daily-dash
```

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `1` – `6` | Jump focus directly to Pane `1` through `6` |
| `Tab` / `Shift+Tab` | Cycle focus across panes |
| `g` | **Live Google Sync**: Pull today's Google Calendar events & Google Docs tasks in background |
| `s` | **Live LAN Scan**: Auto-discover Google Home / Cast / Matter devices & hosts on your Wi-Fi |
| `z` | **Zoom / Maximize** currently focused pane (press `z` again to restore grid) |
| `j` / `k` or `↑` / `↓` | Move cursor inside **Google Home** or **Tasks** panes |
| `Space` / `Enter` | Toggle selected Google Home device (Pane 2) or check/uncheck Task (Pane 4) |
| `p` | Start / Pause Pomodoro timer (when Pane 6 is focused) |
| `h` | Toggle next daily habit streak (when Pane 6 is focused) |
| `r` | Refresh all system metrics and live weather immediately |
| `q` | Quit dashboard |
