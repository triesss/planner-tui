from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, time, timedelta
from typing import Optional

from events import Event


@dataclass
class Task:
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    duration: Optional[timedelta] = None # Added duration field
    completed: bool = False

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["due_date"] = self.due_date.isoformat() if self.due_date else None
        payload["due_time"] = self.due_time.isoformat() if self.due_time else None
        payload["duration"] = self.duration.total_seconds() if self.duration else None # Serialize duration
        return payload

    @staticmethod
    def from_dict(data: dict) -> "Task":
        duration_seconds = data.get("duration")
        duration = timedelta(seconds=duration_seconds) if duration_seconds is not None else None
        return Task(
            title=data["title"],
            description=data.get("description"),
            due_date=date.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            due_time=time.fromisoformat(data["due_time"]) if data.get("due_time") else None,
            duration=duration, # Deserialize duration
            completed=bool(data.get("completed", False)),
        )

    def to_event(self) -> Event:
        return Event(
            title=self.title,
            description=self.description,
            date=self.due_date or date.today(),
            time_start=self.due_time,
            time_end=None,
            duration=self.duration, # Pass duration to event
            all_day=self.due_time is None,
            calendar="local",
            completed=self.completed, # Pass completed status to event
        )
