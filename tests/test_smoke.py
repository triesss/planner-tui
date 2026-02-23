from datetime import date, timedelta, time

from events import Event
from tasks import Task


def test_event_roundtrip():
    event = Event(title="Test", date=date(2024, 1, 1), time_start=time(9,0), duration=timedelta(minutes=30), completed=True)
    payload = event.to_dict()
    restored = Event.from_dict(payload)
    assert restored.title == event.title
    assert restored.date == event.date
    assert restored.duration == event.duration
    assert restored.completed == event.completed


def test_task_to_event():
    task = Task(title="Task", due_date=date(2024, 1, 2), due_time=time(10,0), duration=timedelta(hours=1, minutes=15), completed=True)
    event = task.to_event()
    assert event.title == task.title
    assert event.date == task.due_date
    assert event.time_start == task.due_time
    assert event.duration == task.duration
    assert event.completed == task.completed
