from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

from events import Event
from tasks import Task


def export_json(path: Path, events: List[Event], tasks: List[Task]) -> None:
    payload = {
        "events": [e.to_dict() for e in events],
        "tasks": [t.to_dict() for t in tasks],
    }
    path.write_text(json.dumps(payload, indent=2))


def export_csv(path: Path, events: List[Event], tasks: List[Task]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["type", "title", "date", "time_start", "time_end", "description", "calendar", "completed"])
        for e in events:
            writer.writerow(
                [
                    "event",
                    e.title,
                    e.date.isoformat(),
                    e.time_start.isoformat() if e.time_start else "",
                    e.time_end.isoformat() if e.time_end else "",
                    e.description or "",
                    e.calendar,
                    "",
                ]
            )
        for t in tasks:
            writer.writerow(
                [
                    "task",
                    t.title,
                    t.due_date.isoformat() if t.due_date else "",
                    t.due_time.isoformat() if t.due_time else "",
                    "",
                    t.description or "",
                    "",
                    str(t.completed),
                ]
            )
