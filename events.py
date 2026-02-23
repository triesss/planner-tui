from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from typing import Optional


@dataclass
class Event:
    title: str
    date: date
    description: Optional[str] = None
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    duration: Optional[timedelta] = None
    all_day: bool = False
    calendar: str = "local"
    completed: bool = False # Added completed field

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["date"] = self.date.isoformat()
        payload["time_start"] = self.time_start.isoformat() if self.time_start else None
        payload["time_end"] = self.time_end.isoformat() if self.time_end else None
        payload["duration"] = self.duration.total_seconds() if self.duration else None
        payload["completed"] = self.completed # Serialize completed status
        return payload

    @staticmethod
    def from_dict(data: dict) -> "Event":
        duration_seconds = data.get("duration")
        duration = timedelta(seconds=duration_seconds) if duration_seconds is not None else None
        return Event(
            title=data["title"],
            date=date.fromisoformat(data["date"]),
            description=data.get("description"),
            time_start=time.fromisoformat(data["time_start"]) if data.get("time_start") else None,
            time_end=time.fromisoformat(data["time_end"]) if data.get("time_end") else None,
            duration=duration,
            all_day=bool(data.get("all_day", False)),
            calendar=data.get("calendar", "local"),
            completed=bool(data.get("completed", False)), # Deserialize completed status
        )

    def start_datetime(self) -> datetime:
        if self.time_start:
            return datetime.combine(self.date, self.time_start)
        return datetime.combine(self.date, time.min)

    def end_datetime(self) -> datetime:
        if self.time_end:
            return datetime.combine(self.date, self.time_end)
        return datetime.combine(self.date, time.max)
