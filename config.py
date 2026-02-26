from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path


DATA_DIR = Path(".planner_data")
DATA_DIR.mkdir(exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"


@dataclass
class PomodoroConfig:
    work_min: int = 25
    short_break_min: int = 5
    long_break_min: int = 15
    work_min_alt: int = 50
    short_break_min_alt: int = 10
    long_break_min_alt: int = 30


@dataclass
class ViewConfig:
    week_start_hour: int = 6
    week_end_hour: int = 15
    day_start_hour: int = 8
    day_end_hour: int = 20


@dataclass
class ShortcutConfig:
    start_timer: str = "ctrl s"
    pause_timer: str = "ctrl p"
    stop_timer: str = "ctrl d"
    abort_timer: str = "ctrl a"


@dataclass
class AppConfig:
    pomodoro: PomodoroConfig = field(default_factory=PomodoroConfig)
    view: ViewConfig = field(default_factory=ViewConfig)
    shortcuts: ShortcutConfig = field(default_factory=ShortcutConfig)


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    data = json.loads(CONFIG_PATH.read_text())
    pomodoro = PomodoroConfig(**data.get("pomodoro", {}))
    view = ViewConfig(**data.get("view", {}))
    shortcuts = ShortcutConfig(**data.get("shortcuts", {}))
    return AppConfig(pomodoro=pomodoro, view=view, shortcuts=shortcuts)


def save_config(cfg: AppConfig) -> None:
    payload = {
        "pomodoro": asdict(cfg.pomodoro),
        "view": asdict(cfg.view),
        "shortcuts": asdict(cfg.shortcuts),
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2))


PALETTE = [
    ("header", "black", "light gray"),
    ("footer", "black", "light gray"),
    ("today", "dark red", ""),
    ("has_event", "dark green", ""),
    ("today_focus", "light red", "black"),
    ("selected", "black", "dark cyan"),
    ("day_focus", "black", "dark cyan", "bold"), # Added day focus style
    ("day_focus", "black", "dark cyan", "bold"), # Added day focus style
    ("task", "dark blue", ""),
    ("event", "dark green", ""),
    ("warning", "yellow", ""),
    ("selected_date_focus", "light magenta", "black"),
    ("day_focus", "black", "dark cyan", "bold"), # Added day focus style
    ("day_focus", "black", "dark cyan", "bold"), # Added day focus style
    ("timer", "light magenta", ""),
    ("bold", "", "", "bold"),
]
