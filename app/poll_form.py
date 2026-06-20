from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

from flask import current_app
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.i18n import translate


def _t(lang: str, key: str, **kwargs) -> str:
    return translate(lang, key, **kwargs)


def parse_picked_dates(raw: str | None) -> list[date]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    dates: list[date] = []
    for item in data:
        try:
            dates.append(date.fromisoformat(str(item)))
        except (TypeError, ValueError):
            continue
    return sorted(set(dates))


@dataclass
class PollFormData:
    title: str
    description: str | None
    timezone_name: str
    date_mode: str
    whole_day: bool
    start: date | None
    end: date | None
    picked_dates: list[date]
    day_start: int | None
    day_end: int | None
    slot_minutes: int
    show_names_on_heatmap: bool


def parse_poll_form(
    form,
    *,
    lang: str,
    default_timezone: str = "UTC",
    default_slot_minutes: int = 30,
) -> tuple[PollFormData, list[str]]:
    errors: list[str] = []

    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip() or None
    timezone_name = (form.get("timezone") or default_timezone).strip()
    date_mode = form.get("date_mode", "range")
    if date_mode not in ("range", "pick"):
        date_mode = "range"

    whole_day = form.get("time_mode") == "whole_day"
    show_names_on_heatmap = form.get("show_names_on_heatmap") == "on"
    start = _parse_date(form.get("start_date", ""))
    end = _parse_date(form.get("end_date", ""))
    picked_dates = parse_picked_dates(form.get("picked_dates"))

    day_start = _parse_time_to_minute(form.get("day_start", "08:00"))
    day_end = _parse_time_to_minute(form.get("day_end", "22:00"))
    try:
        slot_minutes = int(form.get("slot_minutes", str(default_slot_minutes)))
    except ValueError:
        slot_minutes = 0

    if whole_day:
        day_start = 0
        day_end = 1440
        slot_minutes = 1440

    if not title:
        errors.append(_t(lang, "error_title_required"))
    if len(title) > 200:
        errors.append(_t(lang, "error_title_too_long"))

    if not start or not end:
        errors.append(_t(lang, "error_dates_required"))
    elif end < start:
        errors.append(_t(lang, "error_end_before_start"))
    elif date_mode == "range" and (end - start).days + 1 > current_app.config["MAX_POLL_DAYS"]:
        errors.append(_t(lang, "error_max_days", days=current_app.config["MAX_POLL_DAYS"]))
    elif date_mode == "pick" and (end - start).days + 1 > current_app.config["MAX_POLL_DAYS"]:
        errors.append(_t(lang, "error_max_days", days=current_app.config["MAX_POLL_DAYS"]))

    if date_mode == "pick":
        if not picked_dates:
            errors.append(_t(lang, "error_picked_dates_required"))
        else:
            for picked in picked_dates:
                if picked < start or picked > end:
                    errors.append(_t(lang, "error_picked_date_out_of_range"))
                    break
            if len(picked_dates) > current_app.config["MAX_POLL_DAYS"]:
                errors.append(_t(lang, "error_max_days", days=current_app.config["MAX_POLL_DAYS"]))

    if not whole_day:
        if day_start is None or day_end is None:
            errors.append(_t(lang, "error_times_required"))
        elif day_end <= day_start:
            errors.append(_t(lang, "error_end_time_before_start"))
        if slot_minutes not in current_app.config["ALLOWED_SLOT_MINUTES"]:
            errors.append(_t(lang, "error_slot_minutes"))
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            errors.append(_t(lang, "error_timezone"))
    else:
        timezone_name = "UTC"

    data = PollFormData(
        title=title,
        description=description,
        timezone_name=timezone_name,
        date_mode=date_mode,
        whole_day=whole_day,
        start=start,
        end=end,
        picked_dates=picked_dates,
        day_start=day_start,
        day_end=day_end,
        slot_minutes=slot_minutes,
        show_names_on_heatmap=show_names_on_heatmap,
    )
    return data, errors


def apply_poll_form(poll, data: PollFormData) -> None:
    poll.title = data.title
    poll.description = data.description
    poll.timezone = data.timezone_name
    poll.date_mode = data.date_mode
    poll.poll_type = "whole_day" if data.whole_day else "times"
    poll.start_date = data.start
    poll.end_date = data.end
    poll.day_start_minute = data.day_start
    poll.day_end_minute = data.day_end
    poll.slot_minutes = data.slot_minutes
    poll.set_picked_dates(data.picked_dates if data.date_mode == "pick" else [])
    poll.show_names_on_heatmap = data.show_names_on_heatmap


def default_form_values(
    *,
    start: date,
    end: date,
    timezone_name: str = "Europe/Berlin",
) -> dict:
    return {
        "date_mode": "range",
        "time_mode": "times",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "picked_dates": "[]",
        "day_start": "08:00",
        "day_end": "22:00",
        "slot_minutes": "30",
        "timezone": timezone_name,
        "show_names_on_heatmap": "",
    }


def poll_to_form_values(poll) -> dict:
    return {
        "title": poll.title,
        "description": poll.description or "",
        "date_mode": poll.date_mode,
        "time_mode": "whole_day" if poll.is_whole_day else "times",
        "start_date": poll.start_date.isoformat(),
        "end_date": poll.end_date.isoformat(),
        "picked_dates": json.dumps([d.isoformat() for d in poll.get_picked_dates()]),
        "day_start": _minute_to_time_value(poll.day_start_minute),
        "day_end": _minute_to_time_value(poll.day_end_minute),
        "slot_minutes": str(poll.slot_minutes),
        "timezone": poll.timezone,
        "show_names_on_heatmap": "on" if poll.show_names_on_heatmap else "",
    }


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_time_to_minute(value: str) -> int | None:
    if not value or ":" not in value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def _minute_to_time_value(minute: int) -> str:
    h, m = divmod(minute, 60)
    return f"{h:02d}:{m:02d}"


def calendar_bounds(start: date, end: date) -> tuple[date, date]:
    grid_start = start - timedelta(days=start.weekday())
    grid_end = end + timedelta(days=6 - end.weekday())
    return grid_start, grid_end
