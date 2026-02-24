from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List, Optional, Union

import urwid
from urwid.font import HalfBlock5x4Font

from config import PALETTE, AppConfig, load_config, save_config
from events import Event
from pomodoro_timer import PomodoroManager
from tasks import Task
from utils.exporter import export_csv, export_json
from utils.storage import load_events, load_tasks, save_events, save_tasks


class ClickableText(urwid.Text):
    def __init__(self, markup, on_click=None, user_data=None):
        super().__init__(markup)
        self.on_click = on_click
        self.user_data = user_data

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and button == 1:
            if self.on_click:
                self.on_click(self.user_data)
                return True
        return super().mouse_event(size, event, button, col, row, focus)


class ClickthroughOverlay(urwid.Overlay):
    def mouse_event(self, size, event, button, col, row, focus):
        handled = super().mouse_event(size, event, button, col, row, focus)
        if not handled and hasattr(self.bottom_w, "mouse_event"):
            return self.bottom_w.mouse_event(size, event, button, col, row, focus)
        return handled


class PlannerApp:
    def __init__(self) -> None:
        self.cfg: AppConfig = load_config()
        self.events: List[Event] = load_events()
        self.tasks: List[Task] = load_tasks()
        self.selected_date: date = date.today()
        self.calendar_focus_date: date = date.today()
        self.day_view_focus_hour: Optional[int] = None  # New state for day view focus
        self.view_mode: str = "month"
        self.message: str = ""
        self.timer = PomodoroManager()

        self.header = urwid.Text("Planner TUI", align="center")
        self.footer = urwid.Text("", align="left")
        self.body = urwid.Columns([urwid.Text("")])
        self.loop: Optional[urwid.MainLoop] = None

        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        view_widget = self._build_view()
        right_widget = self._build_sidebar()
        self.body = urwid.Columns(
            [("weight", 3, view_widget), ("weight", 1, right_widget)],
            dividechars=1,
        )
        self._update_footer()

    def _make_detail_callback(self, item: Union[Event, Task]):
        def callback(_user_data):
            self._open_detail_view(item)
        return callback

    def _build_sidebar(self) -> urwid.Widget:
        tasks = [t for t in self.tasks if not t.completed]  # Filter completed tasks
        task_lines = [ClickableText(("task", f"[ ] {t.title}"), self._make_detail_callback(t)) for t in tasks[:10]]
        if not task_lines:
            task_lines = [urwid.Text("No tasks")]
        timer_line = urwid.Text(self._timer_text())
        upcoming = [e for e in self.events if not e.completed]  # Filter completed events from upcoming
        upcoming.sort(key=lambda e: (e.date, e.time_start or time.min))
        upcoming_lines = [ClickableText(("event", u.title), self._make_detail_callback(u)) for u in upcoming[:5]]  # Display title for upcoming events
        if not upcoming_lines:
            upcoming_lines = [urwid.Text("No upcoming")]
        pile = urwid.Pile(
            [
                urwid.Text(("header", "Tasks")),
                urwid.Divider("-"),
                *task_lines,
                urwid.Divider(),
                urwid.Text(("header", "Pomodoro")),
                timer_line,
                urwid.Divider(),
                urwid.Text(("header", "Upcoming")),
                *upcoming_lines,
            ]
        )
        return urwid.Filler(pile, valign="top")

    def _build_view(self) -> urwid.Widget:
        if self.view_mode == "pomodoro":
            return self._build_pomodoro_view()
        if self.view_mode == "week":
            return self._build_week_view()
        if self.view_mode == "day":
            # When entering day view, set focus to current hour if not already set
            if self.day_view_focus_hour is None:
                self.day_view_focus_hour = datetime.now().hour
            return self._build_day_view()
        return self._build_month_view()

    def _build_month_view(self) -> urwid.Widget:
        cal = calendar.Calendar()
        month_days = list(cal.itermonthdates(self.selected_date.year, self.selected_date.month))
        lines = [
            urwid.Text(self.selected_date.strftime("%B %Y"), align="center"),
            urwid.Text("Mo Tu We Th Fr Sa Su", align="center"),
        ]
        week: List[urwid.Widget] = []
        
        def _make_day_callback(d: date):
            def callback(_user_data):
                self.selected_date = d
                self.calendar_focus_date = d
                self.view_mode = "day"
                # Reset day view focus when changing view
                self.day_view_focus_hour = None
                self._refresh()
            return callback

        for d in month_days:
            label = f"{d.day:2d}"
            has_items = any(e.date == d for e in self.events) or any(
                t.due_date == d for t in self.tasks if t.due_date
            )
            
            click_callback = _make_day_callback(d)
            if d == date.today():
                cell = ClickableText(("today", label), click_callback)
            elif d == self.calendar_focus_date:  # Highlight the focused date
                cell = ClickableText(("selected_date_focus", label), click_callback)
            elif has_items:
                cell = ClickableText(("has_event", label), click_callback)
            else:
                cell = ClickableText(label, click_callback)
                
            if d.month != self.selected_date.month:
                cell = urwid.AttrMap(cell, "warning")
            week.append(cell)
            if len(week) == 7:
                lines.append(urwid.Columns(week, dividechars=1))
                week = []
        return urwid.ListBox(urwid.SimpleFocusListWalker(lines))

    def _build_week_view(self) -> urwid.Widget:
        start = self.selected_date - timedelta(days=self.selected_date.weekday())
        cols = []
        for i in range(7):
            day = start + timedelta(days=i)

            daily_events: List[Event] = [e for e in self.events if e.date == day]
            daily_tasks: List[Task] = [t for t in self.tasks if t.due_date == day]

            timed_items = []
            for e in daily_events:
                if e.time_start:
                    timed_items.append((e.time_start, e))
            for t in daily_tasks:
                if t.due_time:
                    timed_items.append((t.due_time, t))

            timed_items.sort(key=lambda x: x[0])

            lines = [urwid.Text(day.strftime("%a %d"))]

            # Track occupied slots for week view as well for simplified display
            occupied_slots = set()

            for hour in range(self.cfg.view.week_start_hour, self.cfg.view.week_end_hour + 1):
                slot_label = f"{hour:02d}:00"

                # Check if this hour is already occupied by a continuing event/task
                if hour in occupied_slots:
                    lines.append(urwid.Text(f"{slot_label}  (continued)"))
                    continue

                item_for_this_hour = None
                for item_time, item in timed_items:
                    if item_time.hour == hour:  # Check if item starts at this exact hour
                        item_for_this_hour = item
                        # Mark all hours this item occupies as taken
                        item_duration_td = None
                        if isinstance(item, Event):
                            if item.time_end:
                                item_duration_td = datetime.combine(day, item.time_end) - datetime.combine(
                                    day, item.time_start
                                )
                            elif item.duration:
                                item_duration_td = item.duration
                        elif isinstance(item, Task) and item.duration:
                            item_duration_td = item.duration

                        if not item_duration_td:
                            item_duration_td = timedelta(hours=1)  # Default to 1 hour

                        start_hour = item_time.hour
                        end_hour_inclusive = (
                            datetime.combine(day, item_time) + item_duration_td - timedelta(seconds=1)
                        ).hour
                        for h in range(start_hour, end_hour_inclusive + 1):
                            occupied_slots.add(h)
                        break

                if item_for_this_hour:
                    title_str = item_for_this_hour.title
                    duration_str = ""
                    check_mark = "[ ]"  # Initialize check_mark here
                    if isinstance(item_for_this_hour, Event):
                        if item_for_this_hour.time_end:
                            duration_str = f" ({item_for_this_hour.time_end.strftime('%H:%M')})"
                        elif item_for_this_hour.duration:
                            total_minutes = int(item_for_this_hour.duration.total_seconds() / 60)
                            h = total_minutes // 60
                            m = total_minutes % 60
                            duration_str = f" ({h:02d}:{m:02d})"
                        check_mark = "[x]" if item_for_this_hour.completed else "[ ]"
                    elif isinstance(item_for_this_hour, Task):
                        if item_for_this_hour.duration:
                            total_minutes = int(item_for_this_hour.duration.total_seconds() / 60)
                            h = total_minutes // 60
                            m = total_minutes % 60
                            duration_str = f" ({h:02d}:{m:02d})"
                        check_mark = "[x]" if item_for_this_hour.completed else "[ ]"

                    display_text = f"{check_mark} {slot_label} {title_str}{duration_str}"
                    lines.append(ClickableText(("event", display_text), self._make_detail_callback(item_for_this_hour)))
                else:
                    lines.append(urwid.Text(slot_label))

            # Add all-day items for the day
            all_day_items_titles = []
            for item in daily_events:
                if item.all_day:
                    all_day_items_titles.append(f"{'[x]' if item.completed else '[ ]'} {item.title}")
            for item in daily_tasks:
                if not item.due_time:  # assuming tasks without due_time are all-day
                    all_day_items_titles.append(f"{'[x]' if item.completed else '[ ]'} {item.title}")

            if all_day_items_titles:
                lines.insert(1, urwid.Text(("header", "All-day: " + ", ".join(all_day_items_titles))))

            cols.append(urwid.Pile(lines))
        return urwid.Pile(
            [
                urwid.Text(f"Week {start.isoformat()} - {(start + timedelta(days=6)).isoformat()}", align="center"),
                urwid.Columns(cols, dividechars=2),
            ]
        )

    def _build_day_view(self) -> urwid.Widget:
        lines = [urwid.Text(self.selected_date.strftime("%A, %d %B %Y"), align="center")]

        def _make_hour_focus_callback(h):
            def callback(_user_data=None):
                self.day_view_focus_hour = h
                self._refresh()
            return callback

        # Filter and prepare events and tasks for the selected day
        daily_events: List[Event] = [e for e in self.events if e.date == self.selected_date]
        daily_tasks: List[Task] = [t for t in self.tasks if t.due_date == self.selected_date]

        # Combine timed events and tasks, sort by start time
        timed_items = []
        for e in daily_events:
            if e.time_start:
                timed_items.append((e.time_start, e))
        for t in daily_tasks:
            if t.due_time:
                timed_items.append((t.due_time, t))

        timed_items.sort(key=lambda x: x[0])

        # Track occupied slots to prevent overlapping displays
        occupied_slots = {}  # Stores hour -> item

        for hour in range(0, 24):
            slot_label = f"{hour:02d}:00"

            # Determine if this hour is the focused hour for day view navigation
            is_focused_hour = self.day_view_focus_hour == hour
            
            click_cb = _make_hour_focus_callback(hour)

            item_for_this_hour = occupied_slots.get(hour)

            if not item_for_this_hour:
                for item_time, item in timed_items:
                    # Calculate effective start time (for events/tasks)
                    actual_start_dt = datetime.combine(self.selected_date, item_time)

                    # Calculate effective end time or use duration
                    item_end_dt = None
                    item_duration_td = None

                    if isinstance(item, Event):
                        if item.time_end:
                            item_end_dt = datetime.combine(self.selected_date, item.time_end)
                            item_duration_td = item_end_dt - actual_start_dt
                        elif item.duration:
                            item_duration_td = item.duration
                            item_end_dt = actual_start_dt + item_duration_td
                    elif isinstance(item, Task):
                        if item.duration:
                            item_duration_td = item.duration
                            item_end_dt = actual_start_dt + item_duration_td

                    # If no duration or end time, default to 1 hour
                    if not item_duration_td:
                        item_duration_td = timedelta(hours=1)
                        item_end_dt = actual_start_dt + item_duration_td

                    # Check if item starts within this hour slot
                    # We consider an item starting if its start_time is <= current_time_slot and it hasn't been displayed yet
                    # And its start_time is before the next hour slot
                    if actual_start_dt.hour == hour and actual_start_dt.minute == 0:  # Only start events exactly on the hour for now
                        item_for_this_hour = item
                        # Mark all hours this item occupies as taken
                        start_hour = actual_start_dt.hour
                        end_hour_inclusive = (
                            actual_start_dt + item_duration_td - timedelta(seconds=1)
                        ).hour

                        for h in range(start_hour, end_hour_inclusive + 1):
                            occupied_slots[h] = item
                        break  # Found the item for this hour

            if item_for_this_hour:
                title_str = item_for_this_hour.title
                duration_str = ""
                if isinstance(item_for_this_hour, Event):
                    if item_for_this_hour.time_end:
                        duration_str = f" ({item_for_this_hour.time_end.strftime('%H:%M')})"
                    elif item_for_this_hour.duration:
                        total_minutes = int(item_for_this_hour.duration.total_seconds() / 60)
                        h = total_minutes // 60
                        m = total_minutes % 60
                        duration_str = f" ({h:02d}:{m:02d})"
                    check_mark = "[x]" if item_for_this_hour.completed else "[ ]"
                elif isinstance(item_for_this_hour, Task):
                    if item_for_this_hour.duration:
                        total_minutes = int(item_for_this_hour.duration.total_seconds() / 60)
                        h = total_minutes // 60
                        m = total_minutes % 60
                        duration_str = f" ({h:02d}:{m:02d})"
                    check_mark = "[x]" if item_for_this_hour.completed else "[ ]"

                display_text = f"{check_mark} {slot_label} {title_str}{duration_str}"
                text_widget = ClickableText(display_text, self._make_detail_callback(item_for_this_hour))
                lines.append(urwid.AttrMap(text_widget, "day_focus" if is_focused_hour else "event"))
            else:
                # If no item starts and this slot is not explicitly occupied by a continuing event
                if hour not in occupied_slots:
                    now = datetime.now().time()
                    if now.hour == hour and self.selected_date == date.today():
                        text_widget = ClickableText(f"{slot_label} <-- now", click_cb)
                        lines.append(urwid.AttrMap(text_widget, "day_focus" if is_focused_hour else "selected"))
                    else:
                        text_widget = ClickableText(slot_label, click_cb)
                        lines.append(urwid.AttrMap(text_widget, "day_focus" if is_focused_hour else None))

        # Handle all-day tasks/events separately at the top or bottom
        all_day_items_titles = []
        for item in daily_events:
            if item.all_day:
                all_day_items_titles.append(f"{'[x]' if item.completed else '[ ]'} {item.title}")
        for item in daily_tasks:
            if not item.due_time:  # assuming tasks without due_time are all-day
                all_day_items_titles.append(f"{'[x]' if item.completed else '[ ]'} {item.title}")

        if all_day_items_titles:
            lines.insert(1, urwid.Text(("header", "All-day: " + ", ".join(all_day_items_titles))))
            lines.insert(2, urwid.Divider())

        return urwid.ListBox(urwid.SimpleFocusListWalker(lines))

    def _timer_text(self) -> str:
        session = self.timer.current
        if not session:
            return "No active timer"
        remaining = session.remaining()
        status = "paused" if session.paused_at else "running"
        return f"{session.label}: {remaining.seconds // 60:02d}:{remaining.seconds % 60:02d} ({status})"

    def _build_pomodoro_view(self) -> urwid.Widget:
        session = self.timer.current
        if not session:
            return urwid.Filler(urwid.Text("No active timer", align="center"), valign="middle")
        remaining = session.remaining()
        time_text = f"{remaining.seconds // 60:02d}:{remaining.seconds % 60:02d}"
        phase_text = self.timer.phase_display()
        big = urwid.BigText(time_text, HalfBlock5x4Font())
        centered = urwid.Columns(
            [
                ("weight", 1, urwid.SolidFill(" "),),
                ("pack", big),
                ("weight", 1, urwid.SolidFill(" "),),
            ]
        )
        body = urwid.Filler(centered, valign="middle")
        return urwid.Frame(body=body, header=urwid.Text(phase_text, align="center"))

    def _upcoming_events(self, limit: int) -> List[str]:
        # Filter for non-completed upcoming events
        upcoming = sorted([e for e in self.events if not e.completed], key=lambda e: (e.date, e.time_start or time.min))
        result = []
        today = date.today()
        for e in upcoming:
            if e.date >= today:
                label = e.date.isoformat()
                if e.time_start:
                    label += f" {e.time_start.strftime('%H:%M')}"
                result.append(f"{label} {e.title}")
            if len(result) >= limit:
                break
        return result

    def _update_footer(self) -> None:
        def make_shortcut_callback(key: str):
            def callback(_user_data=None):
                self.keypress(key)
            return callback

        if self.view_mode == "pomodoro":
            shortcuts_data = [
                ("a", "abort"), ("s", "skip"), ("p", "pause/resume"), ("q", "quit")
            ]
        else:
            shortcuts_data = [
                ("m", "month"), ("w", "week"), ("d", "day"), ("n", "new event"), ("k", "new task"),
                ("e", "edit event"), ("x", "delete event"), ("E", "edit task"), ("X", "delete task"),
                ("c", "task->event"), ("t", "timer"), ("q", "quit")
            ]
        # Add day view specific shortcuts if in day view
        if self.view_mode == "day":
            shortcuts_data.extend([("up", "scroll"), ("down", "scroll"), ("enter", "view details")])

        widgets = []
        if self.message:
            widgets.append(urwid.Text(self.message + " | "))
            
        for i, (key, label) in enumerate(shortcuts_data):
            # Render keys and labels, making the whole group clickable
            shortcut_markup = [("key", f"{key}"), f" {label}"]
            widgets.append(ClickableText(shortcut_markup, make_shortcut_callback(key)))
            if i < len(shortcuts_data) - 1:
                widgets.append(urwid.Text(" | "))

        footer_flow = urwid.Columns([("pack", w) for w in widgets], dividechars=0)
        self.footer = urwid.Filler(footer_flow, valign="bottom") if not isinstance(self.footer, urwid.Filler) else self.footer
        if isinstance(self.footer, urwid.Filler):
            self.footer.original_widget = footer_flow
        
        # update drawing frame if needed
        if self.loop and hasattr(self.loop.widget, "footer"):
            self.loop.widget.footer = urwid.AttrMap(self.footer, "footer")

    def _set_message(self, msg: str) -> None:
        self.message = msg
        self._update_footer()

    def _refresh(self) -> None:
        self._rebuild_ui()
        if self.loop:
            self.loop.widget = urwid.Frame(
                self.body,
                header=urwid.AttrMap(self.header, "header"),
                footer=urwid.AttrMap(self.footer, "footer"),
            )
            self.loop.draw_screen()

    def keypress(self, key: str) -> None:
        if self.view_mode == "pomodoro":
            if key in ("q", "Q"):
                raise urwid.ExitMainLoop()
            if key == "a":
                self.timer.abort()
                self.view_mode = "month"
                self._refresh()
                return
            if key == "s":
                self.timer.skip()
                self._refresh()
                return
            if key == "p":
                self.timer.toggle_pause()
                self._refresh()
                return

        # Handle calendar navigation in month view
        if self.view_mode == "month":
            if key == "left":
                self.calendar_focus_date -= timedelta(days=1)
                self._refresh()
                return
            if key == "right":
                self.calendar_focus_date += timedelta(days=1)
                self._refresh()
                return
            if key == "up":
                self.calendar_focus_date -= timedelta(days=7)
                self._refresh()
                return
            if key == "down":
                self.calendar_focus_date += timedelta(days=7)
                self._refresh()
                return
            if key == "enter":  # Added: Jump to day view on Enter
                self.selected_date = self.calendar_focus_date
                self.view_mode = "day"
                self._refresh()
                return

        # Handle day view navigation
        if self.view_mode == "day":
            if self.day_view_focus_hour is None:  # Should not happen with current _build_view logic but for safety
                self.day_view_focus_hour = datetime.now().hour

            if key == "up":
                if self.day_view_focus_hour > 0:
                    self.day_view_focus_hour -= 1
                    self._refresh()
                return
            if key == "down":
                if self.day_view_focus_hour < 23:
                    self.day_view_focus_hour += 1
                    self._refresh()
                return
            if key == "enter":  # Open detail view for item at focused hour
                item = self._get_item_at_hour(self.selected_date, self.day_view_focus_hour)
                if item:
                    self._open_detail_view(item)
                else:
                    self._set_message(f"No event or task at {self.day_view_focus_hour:02d}:00")
                return

        # Synchronize selected_date with calendar_focus_date before opening dialogs
        if self.view_mode == "month" and key in ("n", "k"):
            self.selected_date = self.calendar_focus_date

        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()
        if key == "m":
            self.view_mode = "month"
            # Reset day view focus when changing view
            self.day_view_focus_hour = None
            self._refresh()
            return
        if key == "w":
            self.view_mode = "week"
            self.day_view_focus_hour = None
            self._refresh()
            return
        if key == "d":
            self.view_mode = "day"
            # Focus hour will be set by _build_view if None
            self._refresh()
            return
        if key == "n":
            self._open_event_dialog()
            return
        if key == "k":
            self._open_task_dialog()
            return
        if key == "e":
            self._open_event_edit_dialog() # Call without argument for 'find by title'
            return
        if key == "x":
            self._open_event_delete_dialog()
            return
        if key == "E":
            self._open_task_edit_dialog() # Call without argument for 'find by title'
            return
        if key == "X":
            self._open_task_delete_dialog()
            return
        if key == "c":
            self._open_task_convert_dialog()
            return
        if key == "t":
            self._open_timer_dialog()
            return
        # Original left/right key handling, now only outside month view
        if self.view_mode != "month":
            if key == "right":
                self.selected_date += timedelta(days=1)
                self._refresh()
                return
            if key == "left":
                self.selected_date -= timedelta(days=1)
                self._refresh()
                return
        if key == "ctrl s":
            self._start_timer_for_selection()
            return
        if key == "ctrl p":
            self.timer.pause()
            self._refresh()
            return
        if key == "ctrl d":
            self.timer.stop()
            self._refresh()
            return
        if key == "ctrl a":
            self.timer.abort()
            self._refresh()
            return

    def _get_item_at_hour(self, target_date: date, target_hour: int) -> Optional[Union[Event, Task]]:
        """Helper to get the event/task starting at the target_hour on target_date."""
        daily_events: List[Event] = [e for e in self.events if e.date == target_date]
        daily_tasks: List[Task] = [t for t in self.tasks if t.due_date == target_date]

        for item in daily_events + daily_tasks:
            if isinstance(item, Event) and item.time_start and item.time_start.hour == target_hour:
                return item
            if isinstance(item, Task) and item.due_time and item.due_time.hour == target_hour:
                return item
        return None
    
    def _open_detail_view(self, item: Union[Event, Task]) -> None:
        if not self.loop: # Added for testing without full Urwid loop init
            return
        
        detail_lines = [
            urwid.Text(("header", item.title)),
            urwid.Divider(),
            urwid.Text(f"Description: {item.description or 'N/A'}"),
        ]
        
        if isinstance(item, Event):
            detail_lines.append(urwid.Text(f"Date: {item.date.isoformat()}"))
            if item.time_start:
                detail_lines.append(urwid.Text(f"Start: {item.time_start.strftime('%H:%M')}"))
            if item.time_end:
                detail_lines.append(urwid.Text(f"End: {item.time_end.strftime('%H:%M')}"))
            if item.duration:
                total_minutes = int(item.duration.total_seconds() / 60)
                h = total_minutes // 60
                m = total_minutes % 60
                detail_lines.append(urwid.Text(f"Duration: {h:02d}:{m:02d}"))
            detail_lines.append(urwid.Text(f"All day: {item.all_day}"))
            detail_lines.append(urwid.Text(f"Completed: {'Yes' if item.completed else 'No'}"))
        elif isinstance(item, Task):
            if item.due_date:
                detail_lines.append(urwid.Text(f"Due Date: {item.due_date.isoformat()}"))
            if item.due_time:
                detail_lines.append(urwid.Text(f"Due Time: {item.due_time.strftime('%H:%M')}"))
            if item.duration:
                total_minutes = int(item.duration.total_seconds() / 60)
                h = total_minutes // 60
                m = total_minutes % 60
                detail_lines.append(urwid.Text(f"Duration: {h:02d}:{m:02d}"))
            detail_lines.append(urwid.Text(f"Completed: {'Yes' if item.completed else 'No'}"))

        def handle_detail_keypress(key: str):
            if key in ("q", "Q"):
                self._close_overlay()
                # Restore original keypress handler
                self.loop.unhandled_input = self.keypress
                self._refresh()
                return
            if key == "m":
                item.completed = not item.completed
                if isinstance(item, Event):
                    save_events(self.events)
                elif isinstance(item, Task):
                    save_tasks(self.tasks)
                self._set_message(f"'{item.title}' marked as {'done' if item.completed else 'undone'}.")
                self._close_overlay()
                # Restore original keypress handler
                self.loop.unhandled_input = self.keypress
                self._refresh()
                return
            if key == "E": # Edit item from detail view
                self._close_overlay()
                # Do NOT restore original keypress handler here, edit dialog will handle it
                if isinstance(item, Event):
                    self._open_event_edit_dialog(item)
                elif isinstance(item, Task):
                    self._open_task_edit_dialog(item)
                return
            if key == "x": # Delete item from detail view
                if isinstance(item, Event):
                    self.events = [e for e in self.events if e is not item]
                    save_events(self.events)
                elif isinstance(item, Task):
                    self.tasks = [t for t in self.tasks if t is not item]
                    save_tasks(self.tasks)
                self._set_message(f"'{item.title}' deleted.")
                self._close_overlay()
                self.loop.unhandled_input = self.keypress
                self._refresh()
                return
            # Pass unhandled keys back to the main loop if needed, though for an overlay this might not be desired.
            # For now, only 'q' and 'm' are handled.

        # Add buttons/shortcuts for actions
        detail_lines.append(urwid.Divider())
        
        def make_detail_sc_cb(k: str):
            def callback(_ud=None):
                handle_detail_keypress(k)
            return callback

        detail_sc_widgets = [
            urwid.Text("Shortcuts: "),
            ClickableText([("key", "m"), " mark/unmark as done"], make_detail_sc_cb("m")),
            urwid.Text(" | "),
            ClickableText([("key", "E"), " edit"], make_detail_sc_cb("E")),
            urwid.Text(" | "),
            ClickableText([("key", "x"), " delete"], make_detail_sc_cb("x")),
            urwid.Text(" | "),
            ClickableText([("key", "q"), " close"], make_detail_sc_cb("q"))
        ]
        detail_lines.append(urwid.Columns([("pack", w) for w in detail_sc_widgets], dividechars=0))
        
        list_walker = urwid.SimpleFocusListWalker(detail_lines)
        list_box = urwid.ListBox(list_walker)
        
        overlay = ClickthroughOverlay(
            urwid.LineBox(list_box, title="Details"),
            self.loop.widget,
            align="center",
            width=80,
            valign="middle",
            height=15, # Adjust height dynamically based on content if needed
        )
        self.loop.widget = overlay
        # Set a custom keypress handler for this overlay
        self.loop.unhandled_input = handle_detail_keypress

    def _open_event_dialog(self) -> None:
        if not self.loop: # Added for testing without full Urwid loop init
            return
            
        default_start_time = ""
        if self.view_mode == "day" and self.day_view_focus_hour is not None:
            default_start_time = f"{self.day_view_focus_hour:02d}:00"
            
        title_edit = urwid.Edit("Title: ")
        desc_edit = urwid.Edit("Description: ")
        date_edit = urwid.Edit("Date (YYYY-MM-DD): ", self.selected_date.isoformat())
        start_edit = urwid.Edit("Start (HH:MM, optional): ", default_start_time)
        end_edit = urwid.Edit("End (HH:MM, optional): ")
        duration_edit = urwid.Edit("Duration (HH:MM, optional): ") # Added duration input
        all_day_check = urwid.CheckBox("All day", state=False)

        def on_save(_button: urwid.Button) -> None:
            try:
                parsed_date = date.fromisoformat(date_edit.edit_text.strip())
            except ValueError:
                self._set_message("Invalid date")
                return
            start_time = _parse_time(start_edit.edit_text.strip())
            end_time = _parse_time(end_edit.edit_text.strip())
            duration = _parse_timedelta(duration_edit.edit_text.strip()) # Parse duration
            event = Event(
                title=title_edit.edit_text.strip() or "Untitled",
                description=desc_edit.edit_text.strip() or None,
                date=parsed_date,
                time_start=start_time,
                time_end=end_time,
                duration=duration, # Save duration
                all_day=all_day_check.state,
            )
            self.events.append(event)
            save_events(self.events)
            self._close_overlay()
            self._set_message("Event saved")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile = urwid.Pile(
            [
                title_edit,
                desc_edit,
                date_edit,
                start_edit,
                end_edit,
                duration_edit, # Added duration_edit to pile
                all_day_check,
                urwid.Columns([urwid.Button("Save", on_save), urwid.Button("Cancel", on_cancel)]),
            ]
        )
        overlay = ClickthroughOverlay(
            urwid.LineBox(pile, title="New Event"),
            self.loop.widget,
            align="center",
            width=50,
            valign="middle",
            height=13,
        )
        self.loop.widget = overlay

    def _open_task_dialog(self) -> None:
        if not self.loop: # Added for testing without full Urwid loop init
            return
            
        default_due_time = ""
        if self.view_mode == "day" and self.day_view_focus_hour is not None:
            default_due_time = f"{self.day_view_focus_hour:02d}:00"
            
        title_edit = urwid.Edit("Title: ")
        desc_edit = urwid.Edit("Description: ")
        date_edit = urwid.Edit("Due date (YYYY-MM-DD, optional): ", self.selected_date.isoformat())
        time_edit = urwid.Edit("Due time (HH:MM, optional): ", default_due_time)
        duration_edit = urwid.Edit("Duration (HH:MM, optional): ") # Added duration input

        def on_save(_button: urwid.Button) -> None:
            parsed_date = _parse_date(date_edit.edit_text.strip())
            parsed_time = _parse_time(time_edit.edit_text.strip())
            duration = _parse_timedelta(duration_edit.edit_text.strip()) # Parse duration
            task = Task(
                title=title_edit.edit_text.strip() or "Untitled",
                description=desc_edit.edit_text.strip() or None,
                due_date=parsed_date,
                due_time=parsed_time,
                duration=duration, # Save duration
            )
            self.tasks.append(task)
            save_tasks(self.tasks)
            self._close_overlay()
            self._set_message("Task saved")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile = urwid.Pile(
            [
                title_edit,
                desc_edit,
                date_edit,
                time_edit,
                duration_edit, # Added duration_edit to pile
                urwid.Columns([urwid.Button("Save", on_save), urwid.Button("Cancel", on_cancel)]),
            ]
        )
        overlay = ClickthroughOverlay(
            urwid.LineBox(pile, title="New Task"),
            self.loop.widget,
            align="center",
            width=50,
            valign="middle",
            height=11,
        )
        self.loop.widget = overlay

    def _open_event_edit_dialog(self, event_to_edit: Optional[Event] = None) -> None:
        if not self.loop:
            return

        title_edit_text = event_to_edit.title if event_to_edit else ""
        desc_edit_text = event_to_edit.description if event_to_edit and event_to_edit.description else ""
        date_edit_text = event_to_edit.date.isoformat() if event_to_edit and event_to_edit.date else ""
        start_edit_text = event_to_edit.time_start.isoformat() if event_to_edit and event_to_edit.time_start else ""
        end_edit_text = event_to_edit.time_end.isoformat() if event_to_edit and event_to_edit.time_end else ""
        duration_edit_text = f"{int(event_to_edit.duration.total_seconds() / 3600):02d}:{int((event_to_edit.duration.total_seconds() / 60) % 60):02d}" if event_to_edit and event_to_edit.duration else ""
        
        find_title_edit = urwid.Edit("Find title: ", edit_text=title_edit_text) if not event_to_edit else None
        
        new_title = urwid.Edit("New title: ", edit_text=title_edit_text)
        desc_edit = urwid.Edit("New description: ", edit_text=desc_edit_text)
        date_edit = urwid.Edit("New date (YYYY-MM-DD): ", edit_text=date_edit_text)
        start_edit = urwid.Edit("New start (HH:MM, blank = keep): ", edit_text=start_edit_text)
        end_edit = urwid.Edit("New end (HH:MM, blank = keep): ", edit_text=end_edit_text)
        duration_edit = urwid.Edit("New duration (HH:MM, blank = keep): ", edit_text=duration_edit_text)

        def on_save(_button: urwid.Button) -> None:
            event = event_to_edit
            if not event:
                target_title = find_title_edit.edit_text.strip()
                event = next((e for e in self.events if e.title == target_title), None)
            
            if not event:
                self._set_message("Event not found")
                return
            
            # Update event properties
            if new_title.edit_text.strip():
                event.title = new_title.edit_text.strip()
            if desc_edit.edit_text.strip():
                event.description = desc_edit.edit_text.strip()
            
            parsed_date = _parse_date(date_edit.edit_text.strip())
            if parsed_date:
                event.date = parsed_date
            
            if start_edit.edit_text.strip():
                event.time_start = _parse_time(start_edit.edit_text.strip())
            
            if end_edit.edit_text.strip():
                event.time_end = _parse_time(end_edit.edit_text.strip())
            
            if duration_edit.edit_text.strip():
                event.duration = _parse_timedelta(duration_edit.edit_text.strip())
            
            save_events(self.events)
            self._close_overlay()
            self._set_message("Event updated")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile_widgets = []
        if not event_to_edit:
            pile_widgets.append(find_title_edit)
        
        pile_widgets.extend([
            new_title,
            desc_edit,
            date_edit,
            start_edit,
            end_edit,
            duration_edit,
            urwid.Columns([urwid.Button("Save", on_save), urwid.Button("Cancel", on_cancel)]),
        ])
        
        overlay = ClickthroughOverlay(
            urwid.LineBox(urwid.Pile(pile_widgets), title="Edit Event"),
            self.loop.widget,
            align="center",
            width=60,
            valign="middle",
            height=len(pile_widgets) + 3, # Dynamic height
        )
        self.loop.widget = overlay

    def _open_event_delete_dialog(self) -> None:
        title_edit = urwid.Edit("Delete title: ")

        def on_delete(_button: urwid.Button) -> None:
            target = title_edit.edit_text.strip()
            before = len(self.events)
            self.events = [e for e in self.events if e.title != target]
            if len(self.events) == before:
                self._set_message("Event not found")
                return
            save_events(self.events)
            self._close_overlay()
            self._set_message("Event deleted")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile = urwid.Pile(
            [
                title_edit,
                urwid.Columns([urwid.Button("Delete", on_delete), urwid.Button("Cancel", on_cancel)]),
            ]
        )
        overlay = ClickthroughOverlay(
            urwid.LineBox(pile, title="Delete Event"),
            self.loop.widget,
            align="center",
            width=40,
            valign="middle",
            height=6,
        )
        self.loop.widget = overlay

    def _open_task_edit_dialog(self, task_to_edit: Optional[Task] = None) -> None:
        if not self.loop:
            return

        title_edit_text = task_to_edit.title if task_to_edit else ""
        desc_edit_text = task_to_edit.description if task_to_edit and task_to_edit.description else ""
        date_edit_text = task_to_edit.due_date.isoformat() if task_to_edit and task_to_edit.due_date else ""
        time_edit_text = task_to_edit.due_time.isoformat() if task_to_edit and task_to_edit.due_time else ""
        duration_edit_text = f"{int(task_to_edit.duration.total_seconds() / 3600):02d}:{int((task_to_edit.duration.total_seconds() / 60) % 60):02d}" if task_to_edit and task_to_edit.duration else ""

        find_title_edit = urwid.Edit("Find title: ", edit_text=title_edit_text) if not task_to_edit else None

        new_title = urwid.Edit("New title: ", edit_text=title_edit_text)
        desc_edit = urwid.Edit("New description: ", edit_text=desc_edit_text)
        date_edit = urwid.Edit("New due date (YYYY-MM-DD): ", edit_text=date_edit_text)
        time_edit = urwid.Edit("New due time (HH:MM): ", edit_text=time_edit_text)
        duration_edit = urwid.Edit("New duration (HH:MM): ", edit_text=duration_edit_text)

        def on_save(_button: urwid.Button) -> None:
            task = task_to_edit
            if not task:
                target_title = find_title_edit.edit_text.strip()
                task = next((t for t in self.tasks if t.title == target_title), None)

            if not task:
                self._set_message("Task not found")
                return
            
            # Update task properties
            if new_title.edit_text.strip():
                task.title = new_title.edit_text.strip()
            if desc_edit.edit_text.strip():
                task.description = desc_edit.edit_text.strip()

            parsed_date = _parse_date(date_edit.edit_text.strip())
            if parsed_date:
                task.due_date = parsed_date
            
            parsed_time = _parse_time(time_edit.edit_text.strip())
            if parsed_time:
                task.due_time = parsed_time
            
            if duration_edit.edit_text.strip():
                task.duration = _parse_timedelta(duration_edit.edit_text.strip())
            
            save_tasks(self.tasks)
            self._close_overlay()
            self._set_message("Task updated")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile_widgets = []
        if not task_to_edit:
            pile_widgets.append(find_title_edit)
        
        pile_widgets.extend([
            new_title,
            desc_edit,
            date_edit,
            time_edit,
            duration_edit,
            urwid.Columns([urwid.Button("Save", on_save), urwid.Button("Cancel", on_cancel)]),
        ])
        
        overlay = ClickthroughOverlay(
            urwid.LineBox(urwid.Pile(pile_widgets), title="Edit Task"),
            self.loop.widget,
            align="center",
            width=60,
            valign="middle",
            height=len(pile_widgets) + 3, # Dynamic height
        )
        self.loop.widget = overlay

    def _open_task_delete_dialog(self) -> None:
        title_edit = urwid.Edit("Delete title: ")

        def on_delete(_button: urwid.Button) -> None:
            target = title_edit.edit_text.strip()
            before = len(self.tasks)
            self.tasks = [t for t in self.tasks if t.title != target]
            if len(self.tasks) == before:
                self._set_message("Task not found")
                return
            save_tasks(self.tasks)
            self._close_overlay()
            self._set_message("Task deleted")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile = urwid.Pile(
            [
                title_edit,
                urwid.Columns([urwid.Button("Delete", on_delete), urwid.Button("Cancel", on_cancel)]),
            ]
        )
        overlay = ClickthroughOverlay(
            urwid.LineBox(pile, title="Delete Task"),
            self.loop.widget,
            align="center",
            width=40,
            valign="middle",
            height=6,
        )
        self.loop.widget = overlay

    def _open_task_convert_dialog(self) -> None:
        title_edit = urwid.Edit("Task title: ")
        date_edit = urwid.Edit("Event date (YYYY-MM-DD): ", self.selected_date.isoformat())
        time_edit = urwid.Edit("Event start (HH:MM, optional): ")

        def on_convert(_button: urwid.Button) -> None:
            target = title_edit.edit_text.strip()
            task = next((t for t in self.tasks if t.title == target), None)
            if not task:
                self._set_message("Task not found")
                return
            parsed_date = _parse_date(date_edit.edit_text.strip()) or self.selected_date
            parsed_time = _parse_time(time_edit.edit_text.strip())
            event = Event(
                title=task.title,
                description=task.description,
                date=parsed_date,
                time_start=parsed_time,
                time_end=None,
                duration=task.duration,  # Pass task's duration to event
                all_day=parsed_time is None,
                completed=task.completed,  # Pass task's completed status
            )
            self.events.append(event)
            self.tasks = [t for t in self.tasks if t is not task]
            save_events(self.events)
            save_tasks(self.tasks)
            self._close_overlay()
            self._set_message("Task converted to event")
            self._refresh()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile = urwid.Pile(
            [
                title_edit,
                date_edit,
                time_edit,
                urwid.Columns([urwid.Button("Convert", on_convert), urwid.Button("Cancel", on_cancel)]),
            ]
        )
        overlay = ClickthroughOverlay(
            urwid.LineBox(pile, title="Convert Task"),
            self.loop.widget,
            align="center",
            width=50,
            valign="middle",
            height=8,
        )
        self.loop.widget = overlay

    def _open_timer_dialog(self) -> None:
        preset = urwid.RadioButton([], "25/5/15", state=True)
        preset_alt = urwid.RadioButton(preset.group, "50/10/30")
        custom_edit = urwid.Edit("Custom work minutes: ")
        use_custom = urwid.CheckBox("Use custom", state=False)

        def on_start(_button: urwid.Button) -> None:
            if use_custom.state:
                minutes = int(custom_edit.edit_text.strip() or "25")
                self.timer.start_cycle(minutes, self.cfg.pomodoro.short_break_min, self.cfg.pomodoro.long_break_min)
            elif preset_alt.state:
                self.timer.start_cycle(
                    self.cfg.pomodoro.work_min_alt,
                    self.cfg.pomodoro.short_break_min_alt,
                    self.cfg.pomodoro.long_break_min_alt,
                )
            else:
                self.timer.start_cycle(
                    self.cfg.pomodoro.work_min,
                    self.cfg.pomodoro.short_break_min,
                    self.cfg.pomodoro.long_break_min,
                )
            self.view_mode = "pomodoro"
            self._close_overlay()
            self._set_message("Timer started")
            self._refresh()
            self._schedule_tick()

        def on_cancel(_button: urwid.Button) -> None:
            self._close_overlay()

        pile = urwid.Pile(
            [
                urwid.Text("Select preset"),
                preset,
                preset_alt,
                use_custom,
                custom_edit,
                urwid.Columns([urwid.Button("Start", on_start), urwid.Button("Cancel", on_cancel)]),
            ]
        )
        overlay = ClickthroughOverlay(
            urwid.LineBox(pile, title="Pomodoro"),
            self.loop.widget,
            align="center",
            width=45,
            valign="middle",
            height=10,
        )
        self.loop.widget = overlay

    def _start_timer_for_selection(self) -> None:
        self.timer.start_cycle(
            self.cfg.pomodoro.work_min,
            self.cfg.pomodoro.short_break_min,
            self.cfg.pomodoro.long_break_min,
        )
        self.view_mode = "pomodoro"
        self._set_message("Timer started")
        self._refresh()
        self._schedule_tick()

    def _close_overlay(self) -> None:
        # Restore original keypress handler before closing overlay, if it was changed
        if hasattr(self.loop, 'unhandled_input') and self.loop.unhandled_input != self.keypress:
            self.loop.unhandled_input = self.keypress
        self._refresh()

    def export_data(self, path: Path) -> None:
        if path.suffix.lower() == ".csv":
            export_csv(path, self.events, self.tasks)
        else:
            export_json(path, self.events, self.tasks)

    def _schedule_tick(self) -> None:
        if self.loop:
            self.loop.set_alarm_in(1, self._tick)

    def _tick(self, _loop: urwid.MainLoop, _data: object) -> None:
        if self.timer.active:
            self.timer.advance_if_done()
        if self.view_mode == "pomodoro":
            self._refresh()
        if self.timer.active or self.view_mode == "pomodoro":
            self._schedule_tick()


def _parse_date(text: str) -> Optional[date]:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_time(text: str) -> Optional[time]:
    if not text:
        return None
    try:
        return time.fromisoformat(text)
    except ValueError:
        return None


def _parse_timedelta(text: str) -> Optional[timedelta]:
    if not text:
        return None
    try:
        hours, minutes = map(int, text.split(":"))
        return timedelta(hours=hours, minutes=minutes)
    except ValueError:
        return None


def main() -> None:
    app = PlannerApp()
    frame = urwid.Frame(
        app.body,
        header=urwid.AttrMap(app.header, "header"),
        footer=urwid.AttrMap(app.footer, "footer"),
    )
    loop = urwid.MainLoop(frame, palette=PALETTE, unhandled_input=app.keypress)
    app.loop = loop
    app._schedule_tick()
    loop.run()
    save_config(app.cfg)


if __name__ == "__main__":
    main()