from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

from django.core.cache import cache

# pyrefly: ignore [missing-import]
from .attendance_api import fetch_attendance
# pyrefly: ignore [missing-import]
from ..models import UserProfile


def get_overtime_summary(emp_id, start_date, end_date):
    """
    Aggregates overtime data from cached attendance records for a single employee.
    
    Returns:
        dict with:
        - card_punch_ot, requested_ot, weekend_ot, holiday_ot, total_ot (floats)
        - daily_breakdown: list of per-day dicts for charting
        - anomalies: list of punch anomalies
    """
    # Fetch from cache (reuses existing cache key pattern)
    attendance = fetch_attendance(emp_id, start_date, end_date)
    
    # Initialize totals
    card_punch_ot = 0.0
    requested_ot = 0.0
    weekend_ot = 0.0
    holiday_ot = 0.0
    total_ot = 0.0
    
    daily_breakdown = []
    anomalies = []
    
    for record in attendance:
        # Parse OT values - use the display names from formatter
        try:
            cp_ot = float(record.get("Card Punch OT", 0) or 0)
        except (ValueError, TypeError):
            cp_ot = 0.0
            
        try:
            req_ot = float(record.get("Requested OT", 0) or 0)
        except (ValueError, TypeError):
            req_ot = 0.0
            
        try:
            we_ot = float(record.get("Weekend OT", 0) or 0)
        except (ValueError, TypeError):
            we_ot = 0.0
            
        try:
            hol_ot = float(record.get("Holiday OT", 0) or 0)
        except (ValueError, TypeError):
            hol_ot = 0.0
            
        tot_ot = cp_ot + req_ot + we_ot + hol_ot
        
        # Accumulate totals
        card_punch_ot += cp_ot
        requested_ot += req_ot
        weekend_ot += we_ot
        holiday_ot += hol_ot
        total_ot += tot_ot
        
        # Daily breakdown for charting
        raw_date = record.get("Date", "")
        date_str = raw_date.split("T")[0].split(" ")[0] if raw_date else ""
        weekday = record.get("Weekday", "")
        
        # Try to parse weekday as int for display
        weekday_display = ""
        try:
            wd_int = int(weekday)
            weekday_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
            weekday_display = weekday_names.get(wd_int, str(wd_int))
        except (ValueError, TypeError):
            weekday_display = str(weekday) if weekday else ""
        
        daily_breakdown.append({
            "date": date_str,
            "weekday": weekday_display,
            "card_punch_ot": round(cp_ot, 1),
            "requested_ot": round(req_ot, 1),
            "weekend_ot": round(we_ot, 1),
            "holiday_ot": round(hol_ot, 1),
            "total_ot": round(tot_ot, 1)
        })
        
        # Anomaly detection
        # NOTE: GO1 = First Punch In (from formatter: "GO1" -> "In Time")
        #       OUT1 = First Punch Out (from formatter: "OUT1" -> "Out Time")
        work_day = record.get("WorkDay", 0)
        go1 = record.get("In Time", "").strip()  # Punch In
        out1 = record.get("Out Time", "").strip()  # Punch Out
        
        # Check for missing punches on work days
        try:
            work_day_val = float(work_day) if work_day else 0.0
        except (ValueError, TypeError):
            work_day_val = 0.0
        
        if work_day_val > 0:
            # Missing Punch In (GO1) on a work day
            if not go1 or go1 in ("00:00", "—", ""):
                anomalies.append({
                    "date": date_str,
                    "type": "Missing Punch In"
                })
            
            # Missing Punch Out (OUT1) on a work day
            if not out1 or out1 in ("00:00", "—", ""):
                anomalies.append({
                    "date": date_str,
                    "type": "Missing Punch Out"
                })
            
            # Flag punch order issues (OUT1 earlier than GO1 on same calendar day)
            # This suggests a data mapping issue upstream - the biometric system
            # already calculated OT correctly, but we flag this for data quality
            if go1 and out1 and go1 not in ("00:00", "—", "") and out1 not in ("00:00", "—", ""):
                try:
                    go1_parts = go1.split(":")
                    out1_parts = out1.split(":")
                    if len(go1_parts) == 2 and len(out1_parts) == 2:
                        go1_minutes = int(go1_parts[0]) * 60 + int(go1_parts[1])
                        out1_minutes = int(out1_parts[0]) * 60 + int(out1_parts[1])
                        # NOTE: This simple same-day comparison doesn't account for night shift
                        # crossing midnight. For night shifts (20:00-05:00), OUT1 will naturally 
                        # be < GO1 since it crosses to next day. This is expected and valid.
                        # We only flag this as informational - the biometric system already 
                        # calculated OT correctly from the raw punch data.
                        if out1_minutes < go1_minutes:
                            # This could be:
                            # 1. Night shift (valid) - OUT1 is next day early morning
                            # 2. Data mapping issue (invalid) - punches swapped in system
                            # We don't add to anomalies list since we can't determine which case
                            # without additional shift information, but we note it in comments
                            pass  # Biometric system already calculated OT correctly
                except (ValueError, TypeError):
                    pass
    
    # Round final totals
    return {
        "card_punch_ot": round(card_punch_ot, 1),
        "requested_ot": round(requested_ot, 1),
        "weekend_ot": round(weekend_ot, 1),
        "holiday_ot": round(holiday_ot, 1),
        "total_ot": round(total_ot, 1),
        "daily_breakdown": daily_breakdown,
        "anomalies": anomalies
    }


def get_cycle_bounds(reference_date):
    """
    Returns (start_date, end_date) for the 21-to-20 billing cycle containing reference_date.
    
    If reference_date.day >= 21:
        cycle starts on the 21st of that month and ends on the 20th of next month
    Otherwise:
        cycle starts on the 21st of the previous month and ends on the 20th of the current month
    """
    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()
    
    if reference_date.day >= 21:
        # Cycle starts on 21st of current month
        start_date = date(reference_date.year, reference_date.month, 21)
        # Ends on 20th of next month
        end_date = start_date + relativedelta(months=1)
        end_date = date(end_date.year, end_date.month, 20)
    else:
        # Cycle starts on 21st of previous month
        start_date = reference_date - relativedelta(months=1)
        start_date = date(start_date.year, start_date.month, 21)
        # Ends on 20th of current month
        end_date = date(reference_date.year, reference_date.month, 20)
    
    return start_date, end_date


def get_week_bounds(week_num, year=None):
    """
    Returns (start_date, end_date) for a given ISO week number.
    
    Args:
        week_num: Week number (1-52/53)
        year: Year (defaults to current year)
    
    Returns:
        (start_date, end_date) for Monday-Sunday of that week
    """
    if year is None:
        year = datetime.now().year
    
    # ISO week: Week 1 is the week with the first Thursday of the year
    # Find the Monday of week 1
    jan1 = date(year, 1, 1)
    days_to_monday = (7 - jan1.weekday()) % 7  # Days until next Monday
    if days_to_monday == 0:
        days_to_monday = 7 if jan1.weekday() < 3 else 0
    
    week1_monday = jan1 + timedelta(days=days_to_monday)
    
    # Calculate Monday of the requested week
    week_start = week1_monday + timedelta(weeks=week_num - 1)
    week_end = week_start + timedelta(days=6)  # Sunday
    
    return week_start, week_end


def get_all_weeks_in_year(year=None):
    """
    Returns a list of all weeks in a year with their date ranges.
    
    Returns:
        List of dicts: [{"week_num": 1, "start": date, "end": date, "label": "Week 1 (Jan 1 - Jan 7)"}, ...]
    """
    if year is None:
        year = datetime.now().year
    
    weeks = []
    
    # ISO week calculation
    jan1 = date(year, 1, 1)
    days_to_monday = (7 - jan1.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7 if jan1.weekday() < 3 else 0
    
    week1_monday = jan1 + timedelta(days=days_to_monday)
    
    # Generate weeks until we pass the year
    week_num = 1
    current_monday = week1_monday
    
    while current_monday.year <= year:
        week_end = current_monday + timedelta(days=6)
        
        # Only include weeks that overlap with the current year
        if current_monday.year == year or week_end.year == year:
            weeks.append({
                "week_num": week_num,
                "start": current_monday,
                "end": week_end,
                "label": f"Week {week_num} ({current_monday.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')})"
            })
        
        week_num += 1
        current_monday += timedelta(weeks=1)
        
        # Safety limit: max 53 weeks
        if week_num > 53:
            break
    
    return weeks


def get_all_cycles_in_year(year=None):
    """
    Returns a list of all 21-20 billing cycles in a year.
    
    Returns:
        List of dicts: [{"cycle_num": 1, "start": date, "end": date, "label": "January"}, ...]
    """
    if year is None:
        year = datetime.now().year
    
    cycles = []
    cycle_num = 1
    
    # Cycles cover 21st to 20th of the next month. 
    # e.g., Jan is Dec 21 - Jan 20. Feb is Jan 21 - Feb 20.
    for i in range(12):
        if i == 0:
            start_date = date(year - 1, 12, 21)
            end_date = date(year, 1, 20)
        else:
            start_date = date(year, i, 21)
            end_date = date(year, i + 1, 20)
        
        cycles.append({
            "cycle_num": cycle_num,
            "start": start_date,
            "end": end_date,
            "label": end_date.strftime('%B')
        })
        
        cycle_num += 1
    
    return cycles


def get_scope_overtime_summary(dtname4_scope, start_date, end_date):
    """
    Aggregates overtime data across all employees under a given dtName4 scope.
    
    Returns:
        dict with:
        - employees: list of per-employee subtotals
        - scope_total: aggregated totals across all employees
    """
    # Fetch all attendance records for this scope (no employee filter)
    # This reuses the existing cache pattern with emp_id="ALL"
    attendance = fetch_attendance("", start_date, end_date)
    
    # Filter by dtName4 scope
    scope_records = [r for r in attendance if r.get("Day") == dtname4_scope]
    
    # Group by employee
    employee_data = {}
    for record in scope_records:
        emp_id = record.get("Employee ID", "Unknown")
        emp_name = record.get("Employee Name", "Unknown")
        
        if emp_id not in employee_data:
            employee_data[emp_id] = {
                "emp_id": emp_id,
                "emp_name": emp_name,
                "card_punch_ot": 0.0,
                "requested_ot": 0.0,
                "weekend_ot": 0.0,
                "holiday_ot": 0.0,
                "total_ot": 0.0
            }
        
        # Accumulate OT values
        try:
            cp_ot = float(record.get("Card Punch OT", 0) or 0)
        except (ValueError, TypeError):
            cp_ot = 0.0
            
        try:
            req_ot = float(record.get("Requested OT", 0) or 0)
        except (ValueError, TypeError):
            req_ot = 0.0
            
        try:
            we_ot = float(record.get("Weekend OT", 0) or 0)
        except (ValueError, TypeError):
            we_ot = 0.0
            
        try:
            hol_ot = float(record.get("Holiday OT", 0) or 0)
        except (ValueError, TypeError):
            hol_ot = 0.0
            
        tot_ot = cp_ot + req_ot + we_ot + hol_ot
        
        employee_data[emp_id]["card_punch_ot"] += cp_ot
        employee_data[emp_id]["requested_ot"] += req_ot
        employee_data[emp_id]["weekend_ot"] += we_ot
        employee_data[emp_id]["holiday_ot"] += hol_ot
        employee_data[emp_id]["total_ot"] += tot_ot
    
    # Round values and build list
    employees = []
    scope_total = {
        "card_punch_ot": 0.0,
        "requested_ot": 0.0,
        "weekend_ot": 0.0,
        "holiday_ot": 0.0,
        "total_ot": 0.0
    }
    
    for emp_id, emp_data in employee_data.items():
        emp_data["card_punch_ot"] = round(emp_data["card_punch_ot"], 1)
        emp_data["requested_ot"] = round(emp_data["requested_ot"], 1)
        emp_data["weekend_ot"] = round(emp_data["weekend_ot"], 1)
        emp_data["holiday_ot"] = round(emp_data["holiday_ot"], 1)
        emp_data["total_ot"] = round(emp_data["total_ot"], 1)
        
        employees.append(emp_data)
        
        # Accumulate scope totals
        scope_total["card_punch_ot"] += emp_data["card_punch_ot"]
        scope_total["requested_ot"] += emp_data["requested_ot"]
        scope_total["weekend_ot"] += emp_data["weekend_ot"]
        scope_total["holiday_ot"] += emp_data["holiday_ot"]
        scope_total["total_ot"] += emp_data["total_ot"]
    
    # Round scope totals
    for key in scope_total:
        scope_total[key] = round(scope_total[key], 1)
    
    # Sort employees by total OT descending
    employees.sort(key=lambda x: x["total_ot"], reverse=True)
    
    return {
        "employees": employees,
        "scope_total": scope_total,
        "dtname4_scope": dtname4_scope
    }