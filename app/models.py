import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.security import generate_token


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Poll(db.Model):
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    participant_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    poll_type: Mapped[str] = mapped_column(String(20), nullable=False, default="times")
    date_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="range")
    picked_dates: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_start_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=480)
    day_end_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=1320)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    responses: Mapped[list["Response"]] = relationship(
        "Response", back_populates="poll", cascade="all, delete-orphan"
    )

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    @property
    def is_whole_day(self) -> bool:
        return self.poll_type in ("dates_only", "whole_day")

    @property
    def is_dates_only(self) -> bool:
        return self.is_whole_day

    @property
    def is_pick_mode(self) -> bool:
        return self.date_mode == "pick"

    @property
    def is_range_mode(self) -> bool:
        return self.date_mode == "range"

    @property
    def day_count(self) -> int:
        if self.is_pick_mode:
            return len(self.get_picked_dates())
        return (self.end_date - self.start_date).days + 1

    def get_picked_dates(self) -> list[date]:
        try:
            data = json.loads(self.picked_dates)
            if isinstance(data, list):
                dates: list[date] = []
                for item in data:
                    dates.append(date.fromisoformat(str(item)))
                return sorted(set(dates))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return []

    def set_picked_dates(self, dates: list[date]) -> None:
        self.picked_dates = json.dumps(sorted({d.isoformat() for d in dates}))


class Response(db.Model):
    __tablename__ = "responses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), nullable=False)
    edit_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_slots: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    poll: Mapped["Poll"] = relationship("Poll", back_populates="responses")

    def get_slot_indices(self) -> list[int]:
        try:
            data = json.loads(self.selected_slots)
            if isinstance(data, list):
                return [int(x) for x in data]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return []

    def set_slot_indices(self, indices: list[int]) -> None:
        self.selected_slots = json.dumps(sorted(set(int(i) for i in indices)))
