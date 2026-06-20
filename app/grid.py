from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.models import Poll, Response


@dataclass(frozen=True)
class SlotInfo:
    index: int
    day: date
    start_minute: int
    end_minute: int

    @property
    def time_label(self) -> str:
        return f"{_format_minute(self.start_minute)}–{_format_minute(self.end_minute)}"


def _format_minute(minute: int) -> str:
    h, m = divmod(minute, 60)
    return f"{h:02d}:{m:02d}"


def poll_dates(poll: Poll) -> list[date]:
    if poll.is_pick_mode:
        return poll.get_picked_dates()
    dates: list[date] = []
    day = poll.start_date
    while day <= poll.end_date:
        dates.append(day)
        day += timedelta(days=1)
    return dates


def generate_slots(poll: Poll) -> list[SlotInfo]:
    slots: list[SlotInfo] = []
    index = 0
    for day in poll_dates(poll):
        if poll.is_whole_day:
            slots.append(
                SlotInfo(index=index, day=day, start_minute=0, end_minute=1440)
            )
            index += 1
        else:
            minute = poll.day_start_minute
            while minute + poll.slot_minutes <= poll.day_end_minute:
                slots.append(
                    SlotInfo(
                        index=index,
                        day=day,
                        start_minute=minute,
                        end_minute=minute + poll.slot_minutes,
                    )
                )
                index += 1
                minute += poll.slot_minutes
    return slots


def slots_by_day(poll: Poll) -> dict[date, list[SlotInfo]]:
    grouped: dict[date, list[SlotInfo]] = {}
    for slot in generate_slots(poll):
        grouped.setdefault(slot.day, []).append(slot)
    return grouped


def unique_time_rows(poll: Poll) -> list[tuple[int, int]]:
    if poll.is_whole_day:
        return [(0, 1440)]
    rows: list[tuple[int, int]] = []
    minute = poll.day_start_minute
    while minute + poll.slot_minutes <= poll.day_end_minute:
        rows.append((minute, minute + poll.slot_minutes))
        minute += poll.slot_minutes
    return rows


def day_labels(poll: Poll, lang: str = "en") -> list[tuple[date, str, bool]]:
    from app.i18n import format_date_short

    return [
        (day, format_date_short(day, lang), day.weekday() >= 5)
        for day in poll_dates(poll)
    ]


def weekday_headers(lang: str = "en") -> list[str]:
    from app.i18n import weekday_names_short

    return weekday_names_short(lang)


@dataclass(frozen=True)
class CalendarCell:
    day: date
    label: str
    is_weekend: bool
    slot_index: int | None
    in_range: bool


def calendar_weeks(poll: Poll, lang: str = "en") -> list[list[CalendarCell]]:
    from app.i18n import format_calendar_day, weekday_names_short

    if not poll.is_whole_day:
        return []

    active_dates = set(poll_dates(poll))
    indices = slot_map(poll)
    grid_start = poll.start_date - timedelta(days=poll.start_date.weekday())
    grid_end = poll.end_date + timedelta(days=6 - poll.end_date.weekday())

    weeks: list[list[CalendarCell]] = []
    day = grid_start
    while day <= grid_end:
        week: list[CalendarCell] = []
        for _ in weekday_names_short(lang):
            selectable = day in active_dates
            week.append(
                CalendarCell(
                    day=day,
                    label=format_calendar_day(day, lang) if selectable else "",
                    is_weekend=day.weekday() >= 5,
                    slot_index=indices.get((day, 0)) if selectable else None,
                    in_range=selectable,
                )
            )
            day += timedelta(days=1)
        weeks.append(week)
    return weeks


def slot_index_for(poll: Poll, day: date, start_minute: int) -> int | None:
    for slot in generate_slots(poll):
        if slot.day == day and slot.start_minute == start_minute:
            return slot.index
    return None


def compute_heatmap(poll: Poll, responses: list[Response]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for response in responses:
        for index in response.get_slot_indices():
            counts[index] = counts.get(index, 0) + 1
    return counts


@dataclass(frozen=True)
class TopResult:
    label: str
    count: int
    total: int
    attendees: list[str]


def compute_top_results(
    poll: Poll,
    responses: list[Response],
    *,
    limit: int = 5,
    lang: str = "en",
) -> list[TopResult]:
    from app.i18n import format_date_short

    if not responses:
        return []

    heatmap = compute_heatmap(poll, responses)
    if not heatmap:
        return []

    attendees_map = compute_slot_attendees(responses)
    slots_by_index = {slot.index: slot for slot in generate_slots(poll)}
    total = len(responses)

    ranked = sorted(
        ((index, count) for index, count in heatmap.items() if count > 0),
        key=lambda item: (-item[1], item[0]),
    )
    if not ranked:
        return []

    cutoff_count = ranked[min(limit, len(ranked)) - 1][1]
    results: list[TopResult] = []
    for index, count in ranked:
        if count < cutoff_count:
            break
        slot = slots_by_index.get(index)
        if slot is None:
            continue
        day_label = format_date_short(slot.day, lang)
        if poll.is_whole_day:
            label = day_label
        else:
            label = f"{day_label} — {slot.time_label}"
        results.append(
            TopResult(
                label=label,
                count=count,
                total=total,
                attendees=attendees_map.get(index, []),
            )
        )
    return results


def compute_slot_attendees(responses: list[Response]) -> dict[int, list[str]]:
    attendees: dict[int, list[str]] = {}
    for response in responses:
        for index in response.get_slot_indices():
            attendees.setdefault(index, []).append(response.display_name)
    for names in attendees.values():
        names.sort()
    return attendees


def slot_map(poll: Poll) -> dict[tuple[date, int], int]:
    return {(slot.day, slot.start_minute): slot.index for slot in generate_slots(poll)}


def format_minute(minute: int) -> str:
    return _format_minute(minute)


def format_selected_slots_overview(poll: Poll, indices: list[int], lang: str = "en") -> list[str]:
    from app.i18n import format_date_short

    if not indices:
        return []

    index_set = set(indices)
    slots = [slot for slot in generate_slots(poll) if slot.index in index_set]

    if poll.is_whole_day:
        return [format_date_short(slot.day, lang) for slot in slots]

    by_day: dict[date, list[SlotInfo]] = {}
    for slot in slots:
        by_day.setdefault(slot.day, []).append(slot)

    lines: list[str] = []
    for day in sorted(by_day.keys()):
        day_slots = by_day[day]
        day_label = format_date_short(day, lang)
        if len(day_slots) == 1:
            lines.append(f"{day_label} — {day_slots[0].time_label}")
        else:
            times = ", ".join(slot.time_label for slot in day_slots)
            lines.append(f"{day_label} — {times}")
    return lines


def heatmap_color(count: int, total: int) -> str:
    if total <= 0 or count <= 0:
        return "hsl(0, 70%, 92%)"
    ratio = count / total
    hue = int(120 * ratio)
    lightness = 45 + int(25 * ratio)
    return f"hsl({hue}, 65%, {lightness}%)"
