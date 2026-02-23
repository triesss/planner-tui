from __future__ import annotations

from typing import List

from events import Event


class CalendarProvider:
    name = "base"

    def list_events(self) -> List[Event]:
        raise NotImplementedError

    def push_events(self, events: List[Event]) -> None:
        raise NotImplementedError


class LocalCalendarProvider(CalendarProvider):
    name = "local"

    def list_events(self) -> List[Event]:
        return []

    def push_events(self, events: List[Event]) -> None:
        return None


class GoogleCalendarProvider(CalendarProvider):
    name = "google"

    def list_events(self) -> List[Event]:
        return []

    def push_events(self, events: List[Event]) -> None:
        return None


def sync_calendars(local_events: List[Event], remote_events: List[Event]) -> List[Event]:
    merged = {f"{e.title}|{e.date.isoformat()}|{e.time_start}": e for e in local_events}
    for e in remote_events:
        key = f"{e.title}|{e.date.isoformat()}|{e.time_start}"
        if key not in merged:
            merged[key] = e
    return list(merged.values())
