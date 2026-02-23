from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


@dataclass
class PomodoroSession:
    label: str
    duration_min: int
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    elapsed_paused: timedelta = timedelta(0)
    completed: bool = False
    aborted: bool = False

    def start(self) -> None:
        if self.started_at is None:
            self.started_at = datetime.now()

    def pause(self) -> None:
        if self.started_at and not self.paused_at and not self.completed and not self.aborted:
            self.paused_at = datetime.now()

    def resume(self) -> None:
        if self.paused_at:
            self.elapsed_paused += datetime.now() - self.paused_at
            self.paused_at = None

    def stop(self) -> None:
        self.completed = True

    def abort(self) -> None:
        self.aborted = True

    def remaining(self) -> timedelta:
        if not self.started_at:
            return timedelta(minutes=self.duration_min)
        if self.completed or self.aborted:
            return timedelta(0)
        now = self.paused_at or datetime.now()
        elapsed = now - self.started_at - self.elapsed_paused
        remaining = timedelta(minutes=self.duration_min) - elapsed
        return max(remaining, timedelta(0))


class PomodoroManager:
    def __init__(self) -> None:
        self.current: Optional[PomodoroSession] = None
        self.phases: List[Tuple[str, int, str, int]] = []
        self.phase_index: int = 0
        self.active: bool = False

    def start(self, label: str, duration_min: int) -> PomodoroSession:
        session = PomodoroSession(label=label, duration_min=duration_min)
        session.start()
        self.current = session
        self.active = True
        return session

    def start_cycle(self, work_min: int, short_break_min: int, long_break_min: int) -> PomodoroSession:
        self.phases = []
        for i in range(1, 5):
            self.phases.append((f"Work {i}/4", work_min, "work", i))
            if i < 4:
                self.phases.append(("Small Break", short_break_min, "short_break", i))
            else:
                self.phases.append(("Long Break", long_break_min, "long_break", i))
        self.phase_index = 0
        self.active = True
        return self._start_phase()

    def _start_phase(self) -> PomodoroSession:
        label, minutes, _kind, _idx = self.phases[self.phase_index]
        return self.start(label=label, duration_min=minutes)

    def pause(self) -> None:
        if self.current:
            self.current.pause()

    def toggle_pause(self) -> None:
        if not self.current:
            return
        if self.current.paused_at:
            self.current.resume()
        else:
            self.current.pause()

    def resume(self) -> None:
        if self.current:
            self.current.resume()

    def stop(self) -> None:
        if self.current:
            self.current.stop()

    def abort(self) -> None:
        if self.current:
            self.current.abort()
        self.active = False
        self.current = None

    def skip(self) -> None:
        if not self.active or not self.phases:
            return
        self.phase_index = (self.phase_index + 1) % len(self.phases)
        self._start_phase()

    def advance_if_done(self) -> None:
        if not self.current or not self.active:
            return
        if self.current.paused_at:
            return
        if self.current.remaining().total_seconds() > 0:
            return
        self.phase_index = (self.phase_index + 1) % len(self.phases)
        self._start_phase()

    def phase_display(self) -> str:
        if not self.phases or not self.current:
            return ""
        label, _minutes, kind, idx = self.phases[self.phase_index]
        if kind == "work":
            return f"{idx}/4"
        if kind == "short_break":
            return "Small Break"
        return "Long Break"
