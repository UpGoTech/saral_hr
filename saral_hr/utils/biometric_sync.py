import frappe
from frappe.utils import now_datetime, get_datetime, add_days
from frappe.utils.password import get_decrypted_password


def get_machine_password(machine_name):
    try:
        raw = get_decrypted_password("Biometric machine", machine_name, "device_password")
        return int(raw) if raw else 0
    except (ValueError, TypeError):
        return 0
    except Exception:
        return 0


# ─────────────────────────────────────────────
# 1. TEST CONNECTION
# ─────────────────────────────────────────────
@frappe.whitelist()
def test_connection(machine_name):
    if not frappe.db.exists("Biometric machine", machine_name):
        return {
            "success": False,
            "message": "Please save the Biometric Machine record first before testing connection."
        }

    machine = frappe.get_doc("Biometric machine", machine_name)
    conn = None
    try:
        import zk
        z = zk.ZK(
            machine.ip_address,
            port=machine.port or 4370,
            timeout=5,
            password=get_machine_password(machine_name),
            force_udp=False,
            ommit_ping=True,
        )
        conn = z.connect()
        conn.enable_device()
        conn.disconnect()
        frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Connected")
        frappe.db.commit()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Failed")
        frappe.db.commit()
        return {"success": False, "message": str(e)}
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


# ─────────────────────────────────────────────
# 2. FETCH FROM ONE MACHINE (read-only)
# ─────────────────────────────────────────────
def fetch_from_machine(machine_doc):
    import zk
    z = zk.ZK(
        machine_doc.ip_address,
        port=machine_doc.port or 4370,
        timeout=10,
        password=get_machine_password(machine_doc.name),
        force_udp=False,
        ommit_ping=True,
    )
    conn = z.connect()
    try:
        conn.disable_device()
        attendance = conn.get_attendance()
        return attendance
    finally:
        conn.enable_device()
        conn.disconnect()


# ─────────────────────────────────────────────
# 3. FILTER: ONLY NEW DATA AFTER LAST SYNC
# ─────────────────────────────────────────────
def filter_new_records(attendance_list, last_sync_time, fallback_days=3):
    if last_sync_time:
        cutoff = get_datetime(last_sync_time)
    else:
        cutoff = add_days(now_datetime(), -fallback_days)

    return [
        a for a in attendance_list
        if a.timestamp and get_datetime(str(a.timestamp)) > cutoff
    ]


# ─────────────────────────────────────────────
# 4. PUNCH TYPE MAPPING
# ─────────────────────────────────────────────
def get_punch_type(punch_code):
    mapping = {0: "IN", 1: "OUT", 4: "IN", 5: "OUT"}
    return mapping.get(punch_code, "Unknown")


# ─────────────────────────────────────────────
# 5. SAVE RAW LOGS (skip duplicates)
#    - Matched employees: save with name + employee_name  ✓
#    - Unmatched employees: save with employee_name = "Invalid Employee"
# ─────────────────────────────────────────────
def save_raw_logs(machine_name, records, sync_batch):
    saved = 0
    already_exists = 0
    invalid_ids = []   # device IDs with no Frappe employee match

    for record in records:
        punch_time = get_datetime(str(record.timestamp))
        emp_id = str(record.user_id)

        exists = frappe.db.exists("Biometric attendance log", {
            "biometric_machine": machine_name,
            "device_emp_id": emp_id,
            "punch_time": punch_time,
        })
        if exists:
            already_exists += 1
            continue

        # ── FIX: fetch employee_name instead of employee ──
        emp = frappe.db.get_value(
            "Employee",
            {"attendance_device_id": emp_id},
            ["name", "employee_name"],
            as_dict=True,
        )

        if not emp:
            # Track unmapped device IDs (deduplicated per batch)
            if emp_id not in invalid_ids:
                invalid_ids.append(emp_id)

        log = frappe.get_doc({
            "doctype": "Biometric attendance log",
            "biometric_machine": machine_name,
            "device_emp_id": emp_id,
            "employee": emp.name if emp else None,
            "employee_name": emp.employee_name if emp else "Invalid Employee",  # ← FIXED
            "punch_time": punch_time,
            "punch_type": get_punch_type(record.punch),
            "is_processed": 0,
            "sync_batch": sync_batch,
        })
        log.insert(ignore_permissions=True)
        saved += 1

    frappe.db.commit()
    return saved, already_exists, invalid_ids


# ─────────────────────────────────────────────
# 6. MAP DEVICE EMP ID → FRAPPE EMPLOYEE
# ─────────────────────────────────────────────
def map_employees():
    unlinked = frappe.get_all(
        "Biometric attendance log",
        filters={"employee": ["is", "not set"], "is_processed": 0},
        fields=["name", "device_emp_id"],
    )
    for log in unlinked:
        # ── FIX: fetch employee_name instead of employee ──
        emp = frappe.db.get_value(
            "Employee",
            {"attendance_device_id": log.device_emp_id},
            ["name", "employee_name"],
            as_dict=True,
        )
        if emp:
            frappe.db.set_value("Biometric attendance log", log.name, {
                "employee": emp.name,
                "employee_name": emp.employee_name,   # ← FIXED
            })

    frappe.db.commit()


# ─────────────────────────────────────────────
# 7. CREATE EMPLOYEE CHECKIN (optional auto-process)
# ─────────────────────────────────────────────
def push_to_employee_checkin():
    settings = frappe.get_single("Biometric sync settings")
    if not settings.auto_process_to_checkin:
        return

    # Only process logs that have a real employee (skip Invalid Employee)
    logs = frappe.get_all(
        "Biometric attendance log",
        filters={
            "is_processed": 0,
            "employee": ["is", "set"],
            "employee_name": ["!=", "Invalid Employee"],
        },
        fields=["name", "employee", "punch_time", "punch_type"],
    )
    for log in logs:
        try:
            checkin = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": log.employee,
                "time": log.punch_time,
                "log_type": "IN" if log.punch_type == "IN" else "OUT",
                "device_id": "Biometric",
            })
            checkin.insert(ignore_permissions=True)
            frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
        except frappe.DuplicateEntryError:
            frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
        except Exception as e:
            frappe.log_error(f"Checkin error for {log.name}: {e}", "Biometric Sync")

    frappe.db.commit()


# ─────────────────────────────────────────────
# 8. MAIN SYNC — ALL ACTIVE MACHINES
# ─────────────────────────────────────────────
@frappe.whitelist()
def sync_all_machines():
    machines = frappe.get_all(
        "Biometric machine",
        filters={"is_active": 1},
        fields=["name", "ip_address", "port", "device_password",
                "last_sync_time", "machine_name"],
    )

    settings = frappe.get_single("Biometric sync settings")
    fallback_days = settings.default_fetch_days or 3
    sync_batch = now_datetime().strftime("%Y-%m-%d %H:%M:%S")

    results = []
    for m in machines:
        machine_doc = frappe.get_doc("Biometric machine", m.name)
        try:
            raw = fetch_from_machine(machine_doc)
            filtered = filter_new_records(raw, m.last_sync_time, fallback_days)
            saved, already_exists, invalid_ids = save_raw_logs(m.name, filtered, sync_batch)

            frappe.db.set_value("Biometric machine", m.name, {
                "last_sync_time": sync_batch,
                "connection_status": "Connected",
            })
            frappe.db.commit()

            results.append({
                "machine": m.machine_name,
                "fetched": len(filtered),
                "saved": saved,
                "already_exists": already_exists,
                "invalid_ids": invalid_ids,
                "status": "ok",
            })

        except Exception as e:
            frappe.db.set_value("Biometric machine", m.name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {m.machine_name}: {e}", "Biometric Sync")
            results.append({
                "machine": m.machine_name,
                "status": "error",
                "error": str(e),
            })

    map_employees()
    push_to_employee_checkin()

    return results


# ─────────────────────────────────────────────
# 9. PROCESS SINGLE LOG
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_single_log(log_name):
    try:
        log = frappe.get_doc("Biometric attendance log", log_name)

        if not log.employee:
            return {"success": False, "message": "No employee mapped to this log"}

        if log.employee_name == "Invalid Employee":
            return {"success": False, "message": f"Device ID '{log.device_emp_id}' is not mapped to any employee in Frappe. Please set Attendance Device ID on the Employee record."}

        if log.is_processed:
            return {"success": False, "message": "Already processed"}

        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": log.employee,
            "time": log.punch_time,
            "log_type": "IN" if log.punch_type == "IN" else "OUT",
            "device_id": "Biometric",
        })
        checkin.insert(ignore_permissions=True)
        frappe.db.set_value("Biometric attendance log", log_name, "is_processed", 1)
        frappe.db.commit()

        return {"success": True, "message": "Checkin created"}

    except frappe.DuplicateEntryError:
        frappe.db.set_value("Biometric attendance log", log_name, "is_processed", 1)
        frappe.db.commit()
        return {"success": True, "message": "Already exists, marked as processed"}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────
# 10. PROCESS LOGS BY DATE RANGE
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_logs_by_date(start_date, end_date, employee=None, punch_type=None):
    try:
        filters = {
            "is_processed": 0,
            "employee": ["is", "set"],
            "employee_name": ["!=", "Invalid Employee"],
            "punch_time": ["between", [
                start_date + " 00:00:00",
                end_date + " 23:59:59"
            ]],
        }
        if employee:
            filters["employee"] = employee
        if punch_type:
            filters["punch_type"] = punch_type

        logs = frappe.get_all(
            "Biometric attendance log",
            filters=filters,
            fields=["name", "employee", "punch_time", "punch_type"],
            limit=0,
        )

        processed = 0
        failed = 0
        skipped = 0

        for log in logs:
            try:
                checkin = frappe.get_doc({
                    "doctype": "Employee Checkin",
                    "employee": log.employee,
                    "time": log.punch_time,
                    "log_type": "IN" if log.punch_type == "IN" else "OUT",
                    "device_id": "Biometric",
                })
                checkin.insert(ignore_permissions=True)
                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                processed += 1

            except frappe.DuplicateEntryError:
                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                skipped += 1

            except Exception as e:
                frappe.log_error(f"Checkin error for {log.name}: {e}", "Biometric Sync")
                failed += 1

        frappe.db.commit()
        return {
            "success": True,
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────
# 11. SYNC SELECTED MACHINES — BATCH FETCH
# ─────────────────────────────────────────────
@frappe.whitelist()
def sync_selected_machines(machine_names, auto_process=0, offset=0):
    import json

    if isinstance(machine_names, str):
        machine_names = json.loads(machine_names)

    offset = int(offset or 0)
    BATCH_SIZE   = 200   # records per API call / per "Continue" click
    EMIT_EVERY   = 20    # emit realtime every N records
    COMMIT_EVERY = 50    # commit to DB every N inserts

    settings = frappe.get_single("Biometric sync settings")
    fallback_days = settings.default_fetch_days or 3
    sync_batch = now_datetime().strftime("%Y-%m-%d %H:%M:%S")

    results = []

    for machine_name in machine_names:
        if not frappe.db.exists("Biometric machine", machine_name):
            results.append({
                "machine": machine_name,
                "machine_id": machine_name,
                "status": "error",
                "error": "Machine not found"
            })
            continue

        machine_doc = frappe.get_doc("Biometric machine", machine_name)
        try:
            raw = fetch_from_machine(machine_doc)
            filtered = filter_new_records(raw, machine_doc.last_sync_time, fallback_days)

            total          = len(filtered)
            batch          = filtered[offset: offset + BATCH_SIZE]
            batch_num      = (offset // BATCH_SIZE) + 1
            total_in_batch = len(batch)
            remaining      = max(0, total - offset - total_in_batch)

            saved          = 0
            already_exists = 0
            pending_commit = 0
            # Track unmapped IDs seen in this batch (deduplicated)
            invalid_ids_batch = []

            for idx, record in enumerate(batch):
                punch_time = get_datetime(str(record.timestamp))
                emp_id     = str(record.user_id)

                exists = frappe.db.exists("Biometric attendance log", {
                    "biometric_machine": machine_name,
                    "device_emp_id": emp_id,
                    "punch_time": punch_time,
                })

                if exists:
                    already_exists += 1
                else:
                    # ── FIX: fetch employee_name instead of employee ──
                    emp = frappe.db.get_value(
                        "Employee",
                        {"attendance_device_id": emp_id},
                        ["name", "employee_name"],
                        as_dict=True,
                    )

                    if not emp and emp_id not in invalid_ids_batch:
                        invalid_ids_batch.append(emp_id)

                    log = frappe.get_doc({
                        "doctype": "Biometric attendance log",
                        "biometric_machine": machine_name,
                        "device_emp_id": emp_id,
                        "employee": emp.name if emp else None,
                        "employee_name": emp.employee_name if emp else "Invalid Employee",  # ← FIXED
                        "punch_time": punch_time,
                        "punch_type": get_punch_type(record.punch),
                        "is_processed": 0,
                        "sync_batch": sync_batch,
                    })
                    log.insert(ignore_permissions=True)
                    saved += 1
                    pending_commit += 1

                # Commit every COMMIT_EVERY inserts
                if pending_commit >= COMMIT_EVERY:
                    frappe.db.commit()
                    pending_commit = 0

                # Emit realtime every EMIT_EVERY records OR at end of batch
                if (idx + 1) % EMIT_EVERY == 0 or (idx + 1) == total_in_batch:
                    frappe.publish_realtime(
                        event="biometric_fetch_progress",
                        message={
                            "machine_id":      machine_name,
                            "machine":         machine_doc.machine_name,
                            "batch_num":       batch_num,
                            "processed":       idx + 1,
                            "total_in_batch":  total_in_batch,
                            "total":           total,
                            "offset":          offset,
                            "saved":           saved,
                            "already_exists":  already_exists,
                            # Send current list of unmapped IDs seen so far
                            "invalid_ids":     invalid_ids_batch,
                        },
                        user=frappe.session.user
                    )

            # Final commit
            if pending_commit > 0:
                frappe.db.commit()

            # Update machine sync time only on first batch
            if offset == 0:
                frappe.db.set_value("Biometric machine", machine_name, {
                    "last_sync_time":    sync_batch,
                    "connection_status": "Connected",
                })
                frappe.db.commit()

            results.append({
                "machine":        machine_doc.machine_name,
                "machine_id":     machine_name,
                "status":         "ok",
                "total":          total,
                "batch_num":      batch_num,
                "batch_size":     total_in_batch,
                "saved":          saved,
                "already_exists": already_exists,
                "invalid_ids":    invalid_ids_batch,
                "remaining":      remaining,
                "next_offset":    offset + total_in_batch if remaining > 0 else None,
            })

        except Exception as e:
            frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {machine_doc.machine_name}: {e}", "Biometric Sync")
            results.append({
                "machine":    machine_doc.machine_name,
                "machine_id": machine_name,
                "status":     "error",
                "error":      str(e),
            })

    map_employees()

    if int(auto_process or 0):
        push_to_employee_checkin()

    return results


# ─────────────────────────────────────────────
# 12. DEBUG — Check raw vs filtered counts
# ─────────────────────────────────────────────
@frappe.whitelist()
def debug_fetch(machine_name):
    try:
        machine_doc = frappe.get_doc("Biometric machine", machine_name)
        raw = fetch_from_machine(machine_doc)
        settings = frappe.get_single("Biometric sync settings")
        fallback_days = settings.default_fetch_days or 3
        filtered = filter_new_records(raw, machine_doc.last_sync_time, fallback_days)
        sample = [
            {
                "user_id":   str(r.user_id),
                "timestamp": str(r.timestamp),
                "punch":     r.punch
            }
            for r in filtered[:5]
        ]
        return {
            "total_raw":      len(raw),
            "total_filtered": len(filtered),
            "last_sync_time": str(machine_doc.last_sync_time),
            "fallback_days":  fallback_days,
            "sample":         sample
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# 13. ONE-TIME FIX — Repair employee_name on existing records
# ─────────────────────────────────────────────
@frappe.whitelist()
def fix_existing_employee_names():
    """
    Run once from Frappe console to repair old records that have wrong employee_name.
    frappe.call({ method: "saral_hr.utils.biometric_sync.fix_existing_employee_names" })
    """
    logs = frappe.get_all(
        "Biometric attendance log",
        filters={"employee": ["is", "set"]},
        fields=["name", "employee", "employee_name"],
    )
    fixed = 0
    for log in logs:
        correct_name = frappe.db.get_value("Employee", log.employee, "employee_name")
        if correct_name and log.employee_name != correct_name:
            frappe.db.set_value("Biometric attendance log", log.name, "employee_name", correct_name)
            fixed += 1

    # Also fix unlinked records — mark as Invalid Employee
    unlinked = frappe.get_all(
        "Biometric attendance log",
        filters={"employee": ["is", "not set"], "employee_name": ["!=", "Invalid Employee"]},
        fields=["name"],
    )
    for log in unlinked:
        frappe.db.set_value("Biometric attendance log", log.name, "employee_name", "Invalid Employee")
        fixed += 1

    frappe.db.commit()
    return {"fixed": fixed, "message": f"{fixed} records updated successfully"}