# Planner TUI

Terminal-based planner with month, week, and day views, task list, and Pomodoro timer.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Keys

- `m` month view
- `w` week view
- `d` day view
- `n` new event
- `k` new task
- `e` edit event by title
- `x` delete event by title
- `E` edit task by title
- `X` delete task by title
- `c` convert task to event
- `t` pomodoro dialog
- `left` / `right` move selected day
- `Ctrl+S` start timer
- `Ctrl+P` pause timer
- `Ctrl+D` stop timer
- `Ctrl+A` abort timer
- `q` quit

## Data

Data is stored in `.planner_data/` as JSON. Export via `PlannerApp.export_data()` to CSV or JSON.
