import frappe
import math
from frappe.utils import now_datetime, get_datetime, add_days
from frappe.utils.password import get_decrypted_password


def get_machine_password(machine_name):
    try:
        raw = get_decrypted_password("Biometric machine", machine_name, "device_password")
        return int(raw) if raw else 0
    except Exception:
        return 0


# ─────────────────────────────────────────────
# 1. TEST CONNECTION
# ─────────────────────────────────────────────
@frappe.whitelist()
def test_connection(machine_name):
    if not frappe.db.exists("Biometric machine", machine_name):
        return {"success": False, "message": "Please save the record first."}
    machine = frappe.get_doc("Biometric machine", machine_name)
    conn = None
    try:
        import zk
        z = zk.ZK(machine.ip_address, port=machine.port or 4370, timeout=5,
                   password=get_machine_password(machine_name), force_udp=False, ommit_ping=True)
        conn = z.connect()
        conn.enable_device()
        frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Connected")
        frappe.db.commit()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Failed")
        frappe.db.commit()
        return {"success": False, "message": str(e)}
    finally:
        if conn:
            try: conn.disconnect()
            except: pass


# ─────────────────────────────────────────────
# 2. FETCH FROM MACHINE
# ─────────────────────────────────────────────
def fetch_from_machine(machine_doc):
    import zk
    z = zk.ZK(machine_doc.ip_address, port=machine_doc.port or 4370, timeout=10,
               password=get_machine_password(machine_doc.name), force_udp=False, ommit_ping=True)
    conn = z.connect()
    try:
        conn.disable_device()
        return conn.get_attendance()
    finally:
        conn.enable_device()
        conn.disconnect()


# ─────────────────────────────────────────────
# 3. FILTER NEW RECORDS
# ─────────────────────────────────────────────
def filter_new_records(attendance_list, last_sync_time, fallback_days=3):
    if last_sync_time:
        cutoff = get_datetime(str(last_sync_time))
    else:
        cutoff = add_days(now_datetime(), -fallback_days)
    return [a for a in attendance_list
            if a.timestamp and get_datetime(str(a.timestamp)) > cutoff]


# ─────────────────────────────────────────────
# 4. PUNCH TYPE
# ─────────────────────────────────────────────
def get_punch_type(punch_code):
    return {0: "IN", 1: "OUT", 4: "IN", 5: "OUT"}.get(punch_code, "IN")


# ─────────────────────────────────────────────
# 5. MAP EMPLOYEES
# ─────────────────────────────────────────────
def map_employees():
    unlinked = frappe.get_all("Biometric attendance log",
        filters={"employee": ["is", "not set"], "is_processed": 0},
        fields=["name", "device_emp_id"])
    for log in unlinked:
        emp = frappe.db.get_value("Employee",
            {"attendance_device_id": log.device_emp_id},
            ["name", "employee_name"], as_dict=True)
        if emp:
            frappe.db.set_value("Biometric attendance log", log.name,
                {"employee": emp.name, "employee_name": emp.employee_name})
    frappe.db.commit()


# ─────────────────────────────────────────────
# 6. AUTO PROCESS TO CHECKIN
# FIX: use frappe.db.sql to avoid field name issues,
#      handle punch_type None/Unknown safely,
#      log each failure clearly
# ─────────────────────────────────────────────
def push_to_employee_checkin():
    # Fetch unprocessed logs that have an employee mapped
    # Also fetch employee_name from Biometric log so we can set it explicitly
    # and avoid Frappe's fetch_from triggering a re-fetch + length validation error
    logs = frappe.db.sql("""
        SELECT
            bal.name,
            bal.employee,
            bal.employee_name,
            bal.punch_time,
            bal.punch_type
        FROM `tabBiometric attendance log` bal
        WHERE bal.is_processed = 0
          AND bal.employee IS NOT NULL
          AND bal.employee != ''
    """, as_dict=True)

    frappe.log_error(
        f"push_to_employee_checkin: found {len(logs)} unprocessed logs",
        "Biometric Sync Debug"
    )

    created = 0
    skipped = 0
    failed  = 0

    for log in logs:
        try:
            # Safely resolve log_type — default to IN if unknown
            raw_type = (log.punch_type or "").strip().upper()
            log_type = "IN" if raw_type == "IN" else ("OUT" if raw_type == "OUT" else "IN")

            # Skip if Employee Checkin already exists for same employee+time+log_type
            already = frappe.db.exists("Employee Checkin", {
                "employee": log.employee,
                "time":     log.punch_time,
                "log_type": log_type,
            })
            if already:
                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                skipped += 1
                continue

            # Fetch employee_name fresh from Employee master (truncate to 140 chars as safety)
            emp_name = frappe.db.get_value("Employee", log.employee, "employee_name") or log.employee_name or ""
            emp_name = emp_name[:140]

            checkin = frappe.get_doc({
                "doctype":       "Employee Checkin",
                "employee":      log.employee,
                "employee_name": emp_name,   # set explicitly to bypass fetch_from validation
                "time":          log.punch_time,
                "log_type":      log_type,
                "device_id":     "Biometric",
            })
            # ignore_links=True skips fetch_from re-evaluation during insert
            checkin.insert(ignore_permissions=True, ignore_links=True)
            frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
            created += 1

        except frappe.DuplicateEntryError:
            frappe.db.rollback()
            frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
            skipped += 1

        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(
                f"Checkin error for log {log.name} | employee={log.employee} "
                f"| time={log.punch_time} | punch_type={log.punch_type} | error: {e}",
                "Biometric Sync"
            )
            failed += 1

    frappe.db.commit()
    frappe.log_error(
        f"push_to_employee_checkin done: created={created}, skipped={skipped}, failed={failed}",
        "Biometric Sync Debug"
    )
    return {"created": created, "skipped": skipped, "failed": failed}


# ─────────────────────────────────────────────
# 7. PROCESS SINGLE LOG
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_single_log(log_name):
    try:
        log = frappe.get_doc("Biometric attendance log", log_name)
        if not log.employee:
            return {"success": False, "message": "No employee mapped to this log"}
        if log.is_processed:
            return {"success": False, "message": "Already processed"}

        raw_type = (log.punch_type or "").strip().upper()
        log_type = "IN" if raw_type == "IN" else ("OUT" if raw_type == "OUT" else "IN")

        emp_name = frappe.db.get_value("Employee", log.employee, "employee_name") or log.employee_name or ""
        emp_name = emp_name[:140]

        frappe.get_doc({
            "doctype":       "Employee Checkin",
            "employee":      log.employee,
            "employee_name": emp_name,
            "time":          log.punch_time,
            "log_type":      log_type,
            "device_id":     "Biometric",
        }).insert(ignore_permissions=True, ignore_links=True)

        frappe.db.set_value("Biometric attendance log", log_name, "is_processed", 1)
        frappe.db.commit()
        return {"success": True, "message": "Checkin created"}

    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        frappe.db.set_value("Biometric attendance log", log_name, "is_processed", 1)
        frappe.db.commit()
        return {"success": True, "message": "Already exists, marked as processed"}

    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────
# 8. PROCESS LOGS BY DATE RANGE
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_logs_by_date(start_date, end_date, employee=None, punch_type=None):
    try:
        filters = {
            "is_processed": 0,
            "employee": ["is", "set"],
            "punch_time": ["between", [start_date + " 00:00:00", end_date + " 23:59:59"]],
        }
        if employee:   filters["employee"]   = employee
        if punch_type: filters["punch_type"] = punch_type

        logs = frappe.get_all("Biometric attendance log", filters=filters,
            fields=["name", "employee", "employee_name", "punch_time", "punch_type"], limit=0)

        processed = failed = skipped = 0

        for log in logs:
            try:
                raw_type = (log.punch_type or "").strip().upper()
                log_type = "IN" if raw_type == "IN" else ("OUT" if raw_type == "OUT" else "IN")

                already = frappe.db.exists("Employee Checkin", {
                    "employee": log.employee,
                    "time":     log.punch_time,
                    "log_type": log_type,
                })
                if already:
                    frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                    skipped += 1
                    continue

                emp_name = frappe.db.get_value("Employee", log.employee, "employee_name") or log.employee_name or ""
                emp_name = emp_name[:140]

                frappe.get_doc({
                    "doctype":       "Employee Checkin",
                    "employee":      log.employee,
                    "employee_name": emp_name,
                    "time":          log.punch_time,
                    "log_type":      log_type,
                    "device_id":     "Biometric",
                }).insert(ignore_permissions=True, ignore_links=True)

                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                processed += 1

            except frappe.DuplicateEntryError:
                frappe.db.rollback()
                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                skipped += 1

            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(
                    f"Checkin error {log.name}: {e}", "Biometric Sync"
                )
                failed += 1

        frappe.db.commit()
        return {"success": True, "processed": processed, "failed": failed, "skipped": skipped}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────
# 9. SYNC SELECTED MACHINES
# FIX: properly cast auto_process to int from string
# ─────────────────────────────────────────────
@frappe.whitelist()
def sync_selected_machines(machine_names, auto_process=0):
    import json
    if isinstance(machine_names, str):
        machine_names = json.loads(machine_names)

    # FIX: Frappe sends checkbox as string "0"/"1" — cast properly
    try:
        auto_process = int(auto_process)
    except (ValueError, TypeError):
        auto_process = 0

    NUM_BATCHES  = 5
    COMMIT_EVERY = 50

    settings      = frappe.get_single("Biometric sync settings")
    fallback_days = settings.default_fetch_days or 3
    sync_batch    = now_datetime().strftime("%Y-%m-%d %H:%M:%S")

    results = []

    for machine_name in machine_names:
        if not frappe.db.exists("Biometric machine", machine_name):
            results.append({"machine_id": machine_name, "machine": machine_name,
                            "status": "error", "error": "Machine not found"})
            continue

        machine_doc = frappe.get_doc("Biometric machine", machine_name)

        try:
            raw      = fetch_from_machine(machine_doc)
            filtered = filter_new_records(raw, machine_doc.last_sync_time, fallback_days)
            total    = len(filtered)

            batch_size = math.ceil(total / NUM_BATCHES) if total > 0 else 0

            all_invalid_ids = []
            batches_result  = []

            for bn in range(1, NUM_BATCHES + 1):
                b_start = (bn - 1) * batch_size
                b_end   = min(bn * batch_size, total)
                batch   = filtered[b_start:b_end]
                b_size  = len(batch)

                saved          = 0
                already_exists = 0
                pending_commit = 0
                invalid_ids    = []

                for record in batch:
                    punch_time = get_datetime(str(record.timestamp))
                    emp_id     = str(record.user_id)

                    emp = frappe.db.get_value("Employee",
                        {"attendance_device_id": emp_id},
                        ["name", "employee_name"], as_dict=True)

                    if not emp:
                        if emp_id not in invalid_ids:
                            invalid_ids.append(emp_id)
                        if emp_id not in all_invalid_ids:
                            all_invalid_ids.append(emp_id)
                    else:
                        exists = frappe.db.exists("Biometric attendance log", {
                            "biometric_machine": machine_name,
                            "device_emp_id":    emp_id,
                            "punch_time":       punch_time,
                        })
                        if exists:
                            already_exists += 1
                        else:
                            frappe.get_doc({
                                "doctype":           "Biometric attendance log",
                                "biometric_machine": machine_name,
                                "device_emp_id":     emp_id,
                                "employee":          emp.name,
                                "employee_name":     emp.employee_name,
                                "punch_time":        punch_time,
                                "punch_type":        get_punch_type(record.punch),
                                "is_processed":      0,
                                "sync_batch":        sync_batch,
                            }).insert(ignore_permissions=True)
                            saved += 1
                            pending_commit += 1

                    if pending_commit >= COMMIT_EVERY:
                        frappe.db.commit()
                        pending_commit = 0

                if pending_commit > 0:
                    frappe.db.commit()

                batches_result.append({
                    "batch_num":      bn,
                    "total_batches":  NUM_BATCHES,
                    "batch_size":     b_size,
                    "saved":          saved,
                    "already_exists": already_exists,
                    "invalid_count":  len(invalid_ids),
                    "invalid_ids":    invalid_ids,
                })

            frappe.db.set_value("Biometric machine", machine_name, {
                "last_sync_time":    sync_batch,
                "connection_status": "Connected",
            })
            frappe.db.commit()

            results.append({
                "machine":         machine_doc.machine_name,
                "machine_id":      machine_name,
                "status":          "ok",
                "total":           total,
                "num_batches":     NUM_BATCHES,
                "batches":         batches_result,
                "all_invalid_ids": all_invalid_ids,
            })

        except Exception as e:
            frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {machine_doc.machine_name}: {e}", "Biometric Sync")
            results.append({"machine": machine_doc.machine_name, "machine_id": machine_name,
                            "status": "error", "error": str(e)})

    # Always map employees first, then conditionally push to checkin
    map_employees()

    checkin_result = None
    if auto_process == 1:
        checkin_result = push_to_employee_checkin()

    # Attach checkin summary to results for JS to display
    for r in results:
        r["auto_process_result"] = checkin_result

    return results


# ─────────────────────────────────────────────
# 10. SYNC ALL MACHINES (scheduler)
# ─────────────────────────────────────────────
@frappe.whitelist()
def sync_all_machines():
    machines = frappe.get_all("Biometric machine", filters={"is_active": 1},
        fields=["name", "ip_address", "port", "device_password", "last_sync_time", "machine_name"])
    settings      = frappe.get_single("Biometric sync settings")
    fallback_days = settings.default_fetch_days or 3
    sync_batch    = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    for m in machines:
        machine_doc = frappe.get_doc("Biometric machine", m.name)
        try:
            raw      = fetch_from_machine(machine_doc)
            filtered = filter_new_records(raw, m.last_sync_time, fallback_days)
            saved = already_exists = 0
            invalid_ids = []

            for record in filtered:
                punch_time = get_datetime(str(record.timestamp))
                emp_id     = str(record.user_id)
                emp = frappe.db.get_value("Employee", {"attendance_device_id": emp_id},
                                          ["name", "employee_name"], as_dict=True)
                if not emp:
                    if emp_id not in invalid_ids: invalid_ids.append(emp_id)
                    continue
                if frappe.db.exists("Biometric attendance log", {"biometric_machine": m.name,
                        "device_emp_id": emp_id, "punch_time": punch_time}):
                    already_exists += 1
                    continue
                frappe.get_doc({
                    "doctype":           "Biometric attendance log",
                    "biometric_machine": m.name,
                    "device_emp_id":     emp_id,
                    "employee":          emp.name,
                    "employee_name":     emp.employee_name,
                    "punch_time":        punch_time,
                    "punch_type":        get_punch_type(record.punch),
                    "is_processed":      0,
                    "sync_batch":        sync_batch,
                }).insert(ignore_permissions=True)
                saved += 1

            frappe.db.set_value("Biometric machine", m.name,
                {"last_sync_time": sync_batch, "connection_status": "Connected"})
            frappe.db.commit()
            results.append({"machine": m.machine_name, "total": len(filtered),
                "saved": saved, "already_exists": already_exists,
                "invalid_ids": invalid_ids, "status": "ok"})

        except Exception as e:
            frappe.db.set_value("Biometric machine", m.name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {m.machine_name}: {e}", "Biometric Sync")
            results.append({"machine": m.machine_name, "status": "error", "error": str(e)})

    map_employees()
    push_to_employee_checkin()
    return results


# ─────────────────────────────────────────────
# 11. MANUAL TRIGGER (whitelisted for testing)
# ─────────────────────────────────────────────
@frappe.whitelist()
def manual_push_to_checkin():
    """
    Call this from browser console to test push independently:
    frappe.call({method: 'saral_hr.utils.biometric_sync.manual_push_to_checkin', callback: r => console.log(r)})
    """
    result = push_to_employee_checkin()
    return result


# ─────────────────────────────────────────────
# 12. DEBUG
# ─────────────────────────────────────────────
@frappe.whitelist()
def debug_fetch(machine_name):
    try:
        machine_doc   = frappe.get_doc("Biometric machine", machine_name)
        raw           = fetch_from_machine(machine_doc)
        settings      = frappe.get_single("Biometric sync settings")
        fallback_days = settings.default_fetch_days or 3
        filtered      = filter_new_records(raw, machine_doc.last_sync_time, fallback_days)
        return {
            "total_raw":      len(raw),
            "total_filtered": len(filtered),
            "last_sync_time": str(machine_doc.last_sync_time),
            "fallback_days":  fallback_days,
            "sample": [{"user_id": str(r.user_id), "timestamp": str(r.timestamp),
                         "punch": r.punch} for r in filtered[:5]],
        }
    except Exception as e:
        return {"error": str(e)}


@frappe.whitelist()
def debug_unprocessed_logs():
    """
    Check what unprocessed logs exist and why they may not be pushing.
    frappe.call({method: 'saral_hr.utils.biometric_sync.debug_unprocessed_logs', callback: r => console.log(r)})
    """
    all_logs = frappe.db.sql("""
        SELECT name, employee, employee_name, punch_time, punch_type, is_processed
        FROM `tabBiometric attendance log`
        ORDER BY punch_time DESC
        LIMIT 20
    """, as_dict=True)

    unprocessed_with_emp = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabBiometric attendance log`
        WHERE is_processed = 0 AND employee IS NOT NULL AND employee != ''
    """, as_dict=True)

    unprocessed_no_emp = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabBiometric attendance log`
        WHERE is_processed = 0 AND (employee IS NULL OR employee = '')
    """, as_dict=True)

    checkin_count = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabEmployee Checkin`
    """, as_dict=True)

    return {
        "recent_logs":               all_logs,
        "unprocessed_with_employee": unprocessed_with_emp[0].cnt,
        "unprocessed_no_employee":   unprocessed_no_emp[0].cnt,
        "total_employee_checkins":   checkin_count[0].cnt,
    }