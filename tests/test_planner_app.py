from datetime import date, timedelta, time
from main import PlannerApp, _parse_timedelta, Event, Task # Import Event and Task
import urwid
import unittest.mock
from unittest.mock import patch

# Mock load_events and load_tasks globally for test functions that create PlannerApp
# This ensures that PlannerApp uses our test data instead of loading from actual files
@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_month_view_navigation(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    app.view_mode = "month"
    initial_focus_date = app.calendar_focus_date

    # Test 'right' key
    app.keypress("right")
    assert app.calendar_focus_date == initial_focus_date + timedelta(days=1)

    # Test 'left' key
    app.keypress("left") # Should go back to initial_focus_date
    assert app.calendar_focus_date == initial_focus_date

    # Test 'up' key
    app.keypress("up")
    assert app.calendar_focus_date == initial_focus_date - timedelta(days=7)

    # Test 'down' key
    app.keypress("down") # Should go back to initial_focus_date
    assert app.calendar_focus_date == initial_focus_date

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_new_event_task_date_sync(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    app.view_mode = "month"
    app.calendar_focus_date = date(2025, 1, 15) # Set a specific focus date

    # Test 'n' key (new event)
    app.keypress("n")
    assert app.selected_date == date(2025, 1, 15)

    # Reset for next test
    app.calendar_focus_date = date(2025, 2, 20)

    # Test 'k' key (new task)
    app.keypress("k")
    assert app.selected_date == date(2025, 2, 20)

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_month_view_enter_to_day_view(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    app.view_mode = "month"
    test_date = date(2025, 3, 10)
    app.calendar_focus_date = test_date

    app.keypress("enter")

    assert app.view_mode == "day"
    assert app.selected_date == test_date

def test_parse_timedelta():
    assert _parse_timedelta("01:30") == timedelta(hours=1, minutes=30)
    assert _parse_timedelta("00:45") == timedelta(minutes=45)
    assert _parse_timedelta("02:00") == timedelta(hours=2)
    assert _parse_timedelta("") is None
    assert _parse_timedelta("invalid") is None

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_build_day_view_smoke(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    # Ensure it doesn't crash and returns a widget
    widget = app._build_day_view()
    assert isinstance(widget, urwid.Widget)

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_build_week_view_smoke(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    # Ensure it doesn't crash and returns a widget
    widget = app._build_week_view()
    assert isinstance(widget, urwid.Widget)

@patch('main.load_events')
@patch('main.load_tasks')
def test_get_item_at_hour(mock_load_tasks, mock_load_events):
    test_event = Event(title="Morning Meeting", date=date(2025, 1, 1), time_start=time(9,0))
    test_task = Task(title="Morning Task", due_date=date(2025, 1, 1), due_time=time(10,0))
    mock_load_events.return_value = [test_event]
    mock_load_tasks.return_value = [test_task]

    app = PlannerApp()
    
    # Test getting event
    item = app._get_item_at_hour(date(2025, 1, 1), 9)
    assert item == test_event

    # Test getting task
    item = app._get_item_at_hour(date(2025, 1, 1), 10)
    assert item == test_task

    # Test no item at hour
    item = app._get_item_at_hour(date(2025, 1, 1), 11)
    assert item is None

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_open_detail_view_smoke(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    mock_loop = unittest.mock.MagicMock()
    app.loop = mock_loop
    test_event = Event(title="Test Event", date=date(2025, 1, 1), description="Description")
    
    # Ensure it doesn't crash when called with an item
    app._open_detail_view(test_event)
    assert mock_loop.widget is not None # Check that overlay was set

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_open_event_edit_dialog_smoke(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    mock_loop = unittest.mock.MagicMock()
    app.loop = mock_loop
    
    # Ensure it doesn't crash when called without an event (find by title)
    app._open_event_edit_dialog()
    assert mock_loop.widget is not None

    # Ensure it doesn't crash when called with an event
    test_event = Event(title="Edit Me", date=date.today())
    app._open_event_edit_dialog(test_event)
    assert mock_loop.widget is not None

@patch('main.load_events', return_value=[])
@patch('main.load_tasks', return_value=[])
def test_open_task_edit_dialog_smoke(mock_load_tasks, mock_load_events):
    app = PlannerApp()
    mock_loop = unittest.mock.MagicMock()
    app.loop = mock_loop
    
    # Ensure it doesn't crash when called without a task (find by title)
    app._open_task_edit_dialog()
    assert mock_loop.widget is not None

    # Ensure it doesn't crash when called with a task
    test_task = Task(title="Edit Task", due_date=date.today())
    app._open_task_edit_dialog(test_task)
    assert mock_loop.widget is not None