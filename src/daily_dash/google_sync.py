"""Live Google Workspace (Google Calendar, Google Docs Tasks, & Apps Script Status Log) synchronization for DailyDash TUI."""

from __future__ import annotations

import datetime
import json
import re
import shutil
import subprocess
from typing import Any


SHARED_SHOPPING_TASKS_DOC_ID = "1Eq83UhagQoYmPsa1FgzG-nOhEATU6Hld-0CTZIH3BaY"
APPS_SCRIPT_STATUS_DOC_ID = "1K35_qv3yVfncwUodoX-FFTxcB01fscgHzE_cm6MFMFs"

DEFAULT_CALENDARS: list[tuple[str, str]] = [
    ("mjalexja@gmail.com", "Family"),
    ("amarchev91@gmail.com", "Personal"),
    ("marchevskiy@google.com", "Work"),
    ("bsluuk01fgq0b4pnilh7cokh02i1s7o0@import.calendar.google.com", "Hockey"),
    ("avv0m5q0qdejhoq2f3fpqq6epqoei0k8@import.calendar.google.com", "Hockey"),
]


def _format_event_window(start_raw: str, end_raw: str) -> tuple[str, datetime.datetime | None, datetime.datetime | None]:
    """Parse RFC3339 or YYYY-MM-DD timestamps into `HH:MM - HH:MM` display format."""
    if not start_raw:
        return ("All Day", None, None)
    if "T" not in start_raw:
        return ("All Day", None, None)
    try:
        s_dt = datetime.datetime.fromisoformat(start_raw)
        e_dt = datetime.datetime.fromisoformat(end_raw) if end_raw and "T" in end_raw else s_dt
        return (f"{s_dt.strftime('%H:%M')} - {e_dt.strftime('%H:%M')}", s_dt, e_dt)
    except Exception:
        return (start_raw[:16], None, None)


def fetch_google_calendar_events(
    target_date: datetime.date | None = None,
    calendars: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch real events from connected `gcalendar` CLI across configured calendars."""
    if not shutil.which("gcalendar"):
        return []

    day = target_date or datetime.date.today()
    start_iso = f"{day.isoformat()}T00:00:00-08:00"
    end_iso = f"{day.isoformat()}T23:59:59-08:00"
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-8)))

    cal_list = calendars or DEFAULT_CALENDARS
    raw_items: list[tuple[datetime.datetime | None, dict[str, Any]]] = []
    up_next_assigned = False

    for cal_id, cal_label in cal_list:
        try:
            proc = subprocess.run(
                [
                    "gcalendar",
                    "readonly",
                    "events",
                    "--cal",
                    cal_id,
                    "--start",
                    start_iso,
                    "--end",
                    end_iso,
                    "--max",
                    "25",
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=6.0,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            events = json.loads(proc.stdout) or []
            if not isinstance(events, list):
                continue

            for ev in events:
                summary = ev.get("summary") or "(Busy)"
                s_raw = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date") or ""
                e_raw = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date") or ""
                time_str, s_dt, e_dt = _format_event_window(s_raw, e_raw)
                loc = ev.get("location") or ("Villa de Kapuso" if "Daycare" in summary else "SF / Home")
                if "," in loc:
                    loc = loc.split(",")[0].strip()

                status = "upcoming"
                if e_dt and e_dt < now:
                    status = "completed"

                raw_items.append(
                    (
                        s_dt,
                        {
                            "time": time_str,
                            "title": summary,
                            "location": loc,
                            "status": status,
                            "calendar": cal_label,
                        },
                    )
                )
        except Exception:
            continue

    epoch_min = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    raw_items.sort(key=lambda pair: pair[0] or epoch_min)

    results: list[dict[str, Any]] = []
    for _, item in raw_items:
        if item["status"] == "upcoming" and not up_next_assigned:
            item["status"] = "up_next"
            up_next_assigned = True
        results.append(item)

    return results


def fetch_google_docs_tasks(doc_id: str = SHARED_SHOPPING_TASKS_DOC_ID) -> list[dict[str, Any]]:
    """Fetch real tasks and grocery items from the Shared Shopping List & Weekly Tasks Google Doc."""
    if not shutil.which("gdocs"):
        return []

    try:
        proc = subprocess.run(
            ["gdocs", "readonly", "read", doc_id, "--comments=false"],
            capture_output=True,
            text=True,
            timeout=6.0,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        text = proc.stdout
        tasks: list[dict[str, Any]] = []
        section = ""

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                section = line.lstrip("#").strip()
                continue
            if not line.startswith("- "):
                continue

            item_text = line[2:].strip()
            if item_text.endswith(":"):
                continue
            item_text = re.sub(r"\*\*(.*?)\*\*", r"\1", item_text)

            if "Tasks" in section:
                tasks.append(
                    {
                        "id": f"gdoc-t-{len(tasks)+1}",
                        "title": item_text,
                        "priority": "P1" if len(tasks) < 2 else "P2",
                        "project": "Home",
                        "due": "This Week",
                        "done": False,
                    }
                )
            elif "Grocery" in section or "Shopping" in section:
                tasks.append(
                    {
                        "id": f"gdoc-g-{len(tasks)+1}",
                        "title": f"Grocery: {item_text}",
                        "priority": "P2",
                        "project": "Shopping",
                        "due": "Weekly",
                        "done": False,
                    }
                )

        return tasks[:12]
    except Exception:
        return []


def fetch_apps_script_automations(doc_id: str = APPS_SCRIPT_STATUS_DOC_ID) -> list[dict[str, Any]]:
    """Fetch and parse daily Google Apps Script automation statuses from the Status Log Google Doc."""
    if not shutil.which("gdocs"):
        return []

    try:
        proc = subprocess.run(
            ["gdocs", "readonly", "read", doc_id, "--comments=false"],
            capture_output=True,
            text=True,
            timeout=6.0,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        raw = proc.stdout.replace("\\-", "-").replace("\\[", "[").replace("\\]", "]").replace("\\_", "_")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

        # Locate the last "[YYYY-MM-DD ...]" run block
        last_block_idx = 0
        last_check_ts = "Today"
        for idx, ln in enumerate(lines):
            if ln.startswith("[202") and "]" in ln:
                last_block_idx = idx
                last_check_ts = ln.strip("[]").split("—")[0].strip()

        automations: list[dict[str, Any]] = []
        current_item: dict[str, Any] | None = None

        for ln in lines[last_block_idx + 1 :]:
            if ln.startswith("- ") and "(" in ln and ")" in ln:
                name_part = ln[2:].split("(")[0].strip()
                script_id = ln.split("(")[-1].split(")")[0].strip()
                if "Execution Processes API" in name_part:
                    continue
                current_item = {
                    "name": name_part,
                    "script_id": script_id[:14] + "…",
                    "status": "HEALTHY",
                    "runtime": "V8",
                    "timezone": "America/Los_Angeles",
                    "last_checked": last_check_ts,
                    "details": "",
                }
                automations.append(current_item)
            elif current_item is not None and ln.startswith("Status:"):
                parts = [p.strip() for p in ln.split("|")]
                for p in parts:
                    if p.startswith("Status:"):
                        current_item["status"] = p.replace("Status:", "").strip()
                    elif p.startswith("Runtime:"):
                        current_item["runtime"] = p.replace("Runtime:", "").strip()
                    elif p.startswith("Timezone:"):
                        current_item["timezone"] = p.replace("Timezone:", "").strip()
                    elif p.startswith("Last Updated:"):
                        current_item["last_updated"] = p.replace("Last Updated:", "").strip()[:10]
            elif current_item is not None and ln.startswith("Recent Output Verified:"):
                current_item["details"] = ln.replace("Recent Output Verified:", "").strip()

        return automations
    except Exception:
        return []


def sync_config_with_google(cfg: dict[str, Any]) -> dict[str, Any]:
    """Update a config dictionary in-place with live Google Calendar events, Google Docs tasks,
    and daily Apps Script automation health statuses.
    """
    events = fetch_google_calendar_events()
    if events:
        cfg["calendar_events"] = events

    tasks = fetch_google_docs_tasks()
    if tasks:
        cfg["tasks"] = tasks

    automations = fetch_apps_script_automations()
    if automations:
        cfg["automations"] = automations

    return cfg
