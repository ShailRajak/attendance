import json
import time
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from attendance.models import AttendanceRecord, SyncLog
from attendance.services.attendance_service import (
    HEADERS,
    get_attendance_api_url,
)
from attendance.utils.formatter import filter_attendance_data


def get_cycle_dates(today):
    # Current active cycle
    if today.day >= 21:
        curr_start = date(today.year, today.month, 21)
    else:
        if today.month == 1:
            curr_start = date(today.year - 1, 12, 21)
        else:
            curr_start = date(today.year, today.month - 1, 21)
    curr_end = today

    # Previous completed cycle
    prev_end = curr_start - timedelta(days=1)
    if prev_end.month == 1:
        prev_start = date(prev_end.year - 1, 12, 21)
    else:
        prev_start = date(prev_end.year, prev_end.month - 1, 21)

    return (prev_start, prev_end), (curr_start, curr_end)


def get_retention_cutoff(today):
    year = today.year
    month = today.month - 2
    if month <= 0:
        month += 12
        year -= 1
    return date(year, month, 21)


def fetch_single_date_with_status(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    data_payload = {"YYMMDD": date_str}
    payload = {"FunID": "KQ062001", "Language": 3, "Data": data_payload}
    base_url = get_attendance_api_url()

    retries = 3
    for attempt in range(retries):
        try:
            response = requests.post(
                base_url,
                data=json.dumps(payload),
                headers=HEADERS,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("Success"):
                data = result.get("Data", [])
                if isinstance(data, str):
                    data = json.loads(data)

                if isinstance(data, dict):
                    if "Table" in data:
                        data = data["Table"]
                    elif "Rows" in data:
                        data = data["Rows"]
                    else:
                        data = list(data.values())[0]

                if isinstance(data, list):
                    return True, data
        except requests.exceptions.RequestException:
            if attempt < retries - 1:
                time.sleep(0.5)
        except Exception:
            break

    return False, []


def safe_float(val, default=0.0):
    if val in (None, "", "—"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class Command(BaseCommand):
    help = "Synchronize attendance records from external Biometric API to local database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Custom target date in YYYY-MM-DD format (defaults to today)."
        )

    def handle(self, *args, **options):
        # 1. Parse or default today's date
        date_str = options.get("date")
        if date_str:
            try:
                today = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")
                return
        else:
            today = date.today()

        # 2. Calculate cycles and retention cutoff
        (prev_start, prev_end), (curr_start, curr_end) = get_cycle_dates(today)
        retention_cutoff = get_retention_cutoff(today)

        # 3. Determine dates to sync from previous completed cycle
        prev_dates = []
        d = prev_start
        while d <= prev_end:
            prev_dates.append(d)
            d += timedelta(days=1)

        successful_prev_syncs = set(
            SyncLog.objects.filter(
                sync_date__range=(prev_start, prev_end),
                status="SUCCESS"
            ).values_list("sync_date", flat=True)
        )
        unsynced_prev_dates = [d for d in prev_dates if d not in successful_prev_syncs]

        # 4. Determine dates to sync from current active cycle
        curr_dates = []
        d = curr_start
        while d <= curr_end:
            curr_dates.append(d)
            d += timedelta(days=1)

        # Combined target dates
        target_dates = unsynced_prev_dates + curr_dates

        total_created = 0
        total_updated = 0
        total_unchanged = 0
        total_deleted_stale = 0
        failed_dates = []

        # 5. Fetch and synchronize in parallel
        max_workers = min(len(target_dates), 4) if target_dates else 1
        self.stdout.write(
            f"Sync started for target date: {today}\n"
            f"Previous completed cycle: {prev_start} -> {prev_end} (Unsynced days: {len(unsynced_prev_dates)})\n"
            f"Current active cycle: {curr_start} -> {curr_end} (Re-fetching all {len(curr_dates)} days)\n"
            f"Total dates to fetch: {len(target_dates)}"
        )

        if target_dates:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_date = {
                    executor.submit(fetch_single_date_with_status, dt): dt
                    for dt in target_dates
                }

                for future in future_to_date:
                    dt = future_to_date[future]
                    try:
                        success, records = future.result()
                        if not success:
                            failed_dates.append(dt)
                            SyncLog.objects.update_or_create(
                                sync_date=dt,
                                defaults={"status": "FAILED"}
                            )
                            self.stderr.write(f"Sync failed for date: {dt}")
                            continue

                        # Sync to DB
                        created, updated, unchanged, deleted_by_sync = self.sync_date_records(dt, records)
                        total_created += created
                        total_updated += updated
                        total_unchanged += unchanged
                        total_deleted_stale += deleted_by_sync

                        # Update SyncLog
                        SyncLog.objects.update_or_create(
                            sync_date=dt,
                            defaults={
                                "status": "SUCCESS",
                                "records_created": created,
                                "records_updated": updated,
                                "records_unchanged": unchanged
                            }
                        )

                    except Exception as e:
                        failed_dates.append(dt)
                        SyncLog.objects.update_or_create(
                            sync_date=dt,
                            defaults={"status": "FAILED"}
                        )
                        self.stderr.write(f"Unexpected error syncing date {dt}: {e}")

        # 6. Apply retention deletion rule
        # Delete attendance records older than retention_cutoff
        deleted_count = 0
        try:
            records_to_delete = AttendanceRecord.objects.filter(attendance_date__lt=retention_cutoff)
            deleted_count = records_to_delete.count()
            if deleted_count > 0:
                with transaction.atomic():
                    records_to_delete.delete()
                    # Also clean up SyncLogs for deleted dates to save space
                    SyncLog.objects.filter(sync_date__lt=retention_cutoff).delete()
        except Exception as e:
            self.stderr.write(f"Error applying retention rule: {e}")

        # 7. Print summary matching required format
        summary = (
            "============================================================\n"
            "ATTENDANCE SYNC COMPLETED\n"
            "============================================================\n"
            f"Previous cycle: {prev_start} → {prev_end}\n"
            f"Active cycle:   {curr_start} → {curr_end}\n\n"
            f"Created:           {total_created}\n"
            f"Updated:            {total_updated}\n"
            f"Unchanged:        {total_unchanged}\n"
            f"Stale Deleted:    {total_deleted_stale}\n"
            f"Failed:              {len(failed_dates)}\n"
            f"Retention Deleted: {deleted_count}\n"
        )
        if failed_dates:
            summary += "\nFailed dates:\n"
            for fd in sorted(failed_dates):
                summary += f"- {fd}\n"
        summary += "============================================================\n"

        try:
            self.stdout.write(summary)
        except UnicodeEncodeError:
            # Fall back to ASCII arrow "->"
            summary_ascii = summary.replace("→", "->")
            self.stdout.write(summary_ascii)

    def sync_date_records(self, dt, records):
        created_count = 0
        updated_count = 0
        unchanged_count = 0
        deleted_count = 0

        # Get existing records for this date to avoid N+1 queries
        existing_records = {
            r.employee_id: r for r in AttendanceRecord.objects.filter(attendance_date=dt)
        }

        # Format incoming raw records
        formatted_records = filter_attendance_data(records)

        with transaction.atomic():
            seen_employee_ids = set()
            for row in formatted_records:
                emp_id = row.get("Employee ID")
                if not emp_id:
                    continue

                if emp_id in seen_employee_ids:
                    continue
                seen_employee_ids.add(emp_id)

                emp_name = row.get("Employee Name", "")
                in_time = row.get("In Time", "")
                out_time = row.get("Out Time", "")
                work_time = safe_float(row.get("Work Time"))
                working_hours = safe_float(row.get("Working Hours"))
                card_punch_ot = safe_float(row.get("Card Punch OT"))
                requested_ot = safe_float(row.get("Requested OT"))
                weekend_ot = safe_float(row.get("Weekend OT"))
                holiday_ot = safe_float(row.get("Holiday OT"))
                ot4 = safe_float(row.get("OT4"))
                total_ot_all = safe_float(row.get("Total OT All"))
                req_overtime = safe_float(row.get("Req OverTime") or row.get("Req Overtime"))
                approved_ot = safe_float(row.get("Approved OT"))
                wt_id = row.get("WT ID", "")
                wt_type_no = row.get("WT Type No", "")
                attendance_source = row.get("Attendance Source", "")
                day = row.get("Day", "")
                if not day or day == "AD":
                    known_day = (
                        AttendanceRecord.objects.filter(employee_id=emp_id)
                        .exclude(day="")
                        .exclude(day="AD")
                        .values_list("day", flat=True)
                        .first()
                    )
                    if known_day:
                        day = known_day
                attendance_status = row.get("Attendance Status", "")
                shift = row.get("Shift", "")
                mobile = row.get("Mobile", "")
                late_minutes = safe_float(row.get("Late Minutes"))
                leave_type = row.get("Leave Type", "")
                workday = str(row.get("WorkDay")) if row.get("WorkDay") is not None else ""
                weekday = str(row.get("Weekday")) if row.get("Weekday") is not None else ""

                # NOTE: All OT fields are stored exactly as the biometric API
                # computes them. The API's own engine already correctly classifies
                # OT into card_punch (OverTime), requested (OverTime1),
                # weekend (OverTime2), holiday (OverTime3), and total (OverTimeAll).
                # Do NOT apply any local overrides or caps here.

                existing = existing_records.get(emp_id)
                if not existing:
                    # INSERT
                    AttendanceRecord.objects.create(
                        employee_id=emp_id,
                        employee_name=emp_name,
                        attendance_date=dt,
                        in_time=in_time,
                        out_time=out_time,
                        work_time=work_time,
                        working_hours=working_hours,
                        card_punch_ot=card_punch_ot,
                        requested_ot=requested_ot,
                        weekend_ot=weekend_ot,
                        holiday_ot=holiday_ot,
                        ot4=ot4,
                        total_ot_all=total_ot_all,
                        req_overtime=req_overtime,
                        approved_ot=approved_ot,
                        wt_id=wt_id,
                        wt_type_no=wt_type_no,
                        attendance_source=attendance_source,
                        day=day,
                        attendance_status=attendance_status,
                        shift=shift,
                        mobile=mobile,
                        late_minutes=late_minutes,
                        leave_type=leave_type,
                        workday=workday,
                        weekday=weekday,
                    )
                    created_count += 1
                else:
                    # UPDATE check
                    changed = (
                        existing.employee_name != emp_name or
                        existing.in_time != in_time or
                        existing.out_time != out_time or
                        existing.work_time != work_time or
                        existing.working_hours != working_hours or
                        existing.card_punch_ot != card_punch_ot or
                        existing.requested_ot != requested_ot or
                        existing.weekend_ot != weekend_ot or
                        existing.holiday_ot != holiday_ot or
                        existing.ot4 != ot4 or
                        existing.total_ot_all != total_ot_all or
                        existing.req_overtime != req_overtime or
                        existing.approved_ot != approved_ot or
                        existing.wt_id != wt_id or
                        existing.wt_type_no != wt_type_no or
                        existing.attendance_source != attendance_source or
                        existing.day != day or
                        existing.attendance_status != attendance_status or
                        existing.shift != shift or
                        existing.mobile != mobile or
                        existing.late_minutes != late_minutes or
                        existing.leave_type != leave_type or
                        existing.workday != workday or
                        existing.weekday != weekday
                    )

                    if changed:
                        existing.employee_name = emp_name
                        existing.in_time = in_time
                        existing.out_time = out_time
                        existing.work_time = work_time
                        existing.working_hours = working_hours
                        existing.card_punch_ot = card_punch_ot
                        existing.requested_ot = requested_ot
                        existing.weekend_ot = weekend_ot
                        existing.holiday_ot = holiday_ot
                        existing.ot4 = ot4
                        existing.total_ot_all = total_ot_all
                        existing.req_overtime = req_overtime
                        existing.approved_ot = approved_ot
                        existing.wt_id = wt_id
                        existing.wt_type_no = wt_type_no
                        existing.attendance_source = attendance_source
                        existing.day = day
                        existing.attendance_status = attendance_status
                        existing.shift = shift
                        existing.mobile = mobile
                        existing.late_minutes = late_minutes
                        existing.leave_type = leave_type
                        existing.workday = workday
                        existing.weekday = weekday
                        existing.save()
                        updated_count += 1
                    else:
                        unchanged_count += 1

            # Delete stale records: any DB record for this date whose employee_id
            # was NOT returned by the latest API batch. This prevents previously
            # synced records (now removed from the source system) from inflating
            # aggregates like Card Punch OT.
            if seen_employee_ids:
                stale_ids = set(existing_records.keys()) - seen_employee_ids
                if stale_ids:
                    del_result = AttendanceRecord.objects.filter(
                        attendance_date=dt, employee_id__in=stale_ids
                    ).delete()
                    deleted_count = del_result[0]

        return created_count, updated_count, unchanged_count, deleted_count

