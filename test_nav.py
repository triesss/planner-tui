import calendar
from datetime import date, timedelta

selected_date = date(2026, 6, 15)
calendar_focus_date = date(2026, 7, 5)

for key in ["right", "left"]:
    print(f"--- Key: {key} ---")
    cal = calendar.Calendar()
    month_days = list(cal.itermonthdates(selected_date.year, selected_date.month))
    print(f"Current grid ends at {month_days[-1]}")
    
    if key == "right":
        calendar_focus_date = month_days[-1]
        calendar_focus_date += timedelta(days=1)
    elif key == "left":
        calendar_focus_date = month_days[0]
        calendar_focus_date -= timedelta(days=1)

    print(f"New focus date: {calendar_focus_date}")
    
    if calendar_focus_date not in month_days:
        print(f"Focus date {calendar_focus_date} is NOT in current grid")
        selected_date = calendar_focus_date
    else:
        print(f"Focus date IS in grid.")
        
    cal2 = calendar.Calendar()
    new_month_days = list(cal2.itermonthdates(selected_date.year, selected_date.month))
    
    print(f"New grid is from {new_month_days[0]} to {new_month_days[-1]}")
    print(f"Is focus date in new grid? {calendar_focus_date in new_month_days}")

