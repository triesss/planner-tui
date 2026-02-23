from __future__ import annotations

import json
from pathlib import Path
from typing import List

from events import Event
from tasks import Task


DATA_DIR = Path(".planner_data")
DATA_DIR.mkdir(exist_ok=True)
EVENTS_PATH = DATA_DIR / "events.json"
TASKS_PATH = DATA_DIR / "tasks.json"


def load_events() -> List[Event]:
    if not EVENTS_PATH.exists():
        return []
    data = json.loads(EVENTS_PATH.read_text())
    return [Event.from_dict(item) for item in data]


def save_events(events: List[Event]) -> None:
    EVENTS_PATH.write_text(json.dumps([e.to_dict() for e in events], indent=2))


def load_tasks() -> List[Task]:
    if not TASKS_PATH.exists():
        return []
    data = json.loads(TASKS_PATH.read_text())
    return [Task.from_dict(item) for item in data]


def save_tasks(tasks: List[Task]) -> None:
    TASKS_PATH.write_text(json.dumps([t.to_dict() for t in tasks], indent=2))
