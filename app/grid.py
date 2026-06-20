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


def generate_slots(poll: Poll) -> list[SlotInfo]:
    slots: list[SlotInfo] = []
    index = 0
    day = poll.start_date
    while day <= poll.end_date:
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
        day += timedelta(days=1)
    return slots


def slots_by_day(poll: Poll) -> dict[date, list[SlotInfo]]:
    grouped: dict[date, list[SlotInfo]] = {}
    for slot in generate_slots(poll):
        grouped.setdefault(slot.day, []).append(slot)
    return grouped


def unique_time_rows(poll: Poll) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    minute = poll.day_start_minute
    while minute + poll.slot_minutes <= poll.day_end_minute:
        rows.append((minute, minute + poll.slot_minutes))
        minute += poll.slot_minutes
    return rows


def day_labels(poll: Poll, lang: str = "en") -> list[tuple[date, str]]:
    from app.i18n import format_date_short

    labels: list[tuple[date, str]] = []
    day = poll.start_date
    while day <= poll.end_date:
        labels.append((day, format_date_short(day, lang)))
        day += timedelta(days=1)
    return labels


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


def slot_map(poll: Poll) -> dict[tuple[date, int], int]:
    return {(slot.day, slot.start_minute): slot.index for slot in generate_slots(poll)}


def format_minute(minute: int) -> str:
    return _format_minute(minute)


def heatmap_color(count: int, total: int) -> str:
    if total <= 0 or count <= 0:
        return "hsl(0, 70%, 92%)"
    ratio = count / total
    hue = int(120 * ratio)
    lightness = 45 + int(25 * ratio)
    return f"hsl({hue}, 65%, {lightness}%)"
