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
#    IMPORTANT: uses original_sync_time (the value BEFORE this sync started)
#    so all batches filter from the same cutoff point
# ─────────────────────────────────────────────
def filter_new_records(attendance_list, last_sync_time, fallback_days=3):
    if last_sync_time:
        cutoff = get_datetime(str(last_sync_time))
    else:
        cutoff = add_days(now_datetime(), -fallback_days)
    return [a for a in attendance_list if a.timestamp and get_datetime(str(a.timestamp)) > cutoff]


# ─────────────────────────────────────────────
# 4. PUNCH TYPE
# ─────────────────────────────────────────────
def get_punch_type(punch_code):
    return {0: "IN", 1: "OUT", 4: "IN", 5: "OUT"}.get(punch_code, "Unknown")


# ─────────────────────────────────────────────
# 5. MAP EMPLOYEES
# ─────────────────────────────────────────────
def map_employees():
    unlinked = frappe.get_all("Biometric attendance log",
        filters={"employee": ["is", "not set"], "is_processed": 0},
        fields=["name", "device_emp_id"])
    for log in unlinked:
        emp = frappe.db.get_value("Employee", {"attendance_device_id": log.device_emp_id},
                                  ["name", "employee_name"], as_dict=True)
        if emp:
            frappe.db.set_value("Biometric attendance log", log.name,
                                {"employee": emp.name, "employee_name": emp.employee_name})
    frappe.db.commit()


# ─────────────────────────────────────────────
# 6. AUTO PROCESS TO CHECKIN
# ─────────────────────────────────────────────
def push_to_employee_checkin():
    settings = frappe.get_single("Biometric sync settings")
    if not settings.auto_process_to_checkin:
        return
    logs = frappe.get_all("Biometric attendance log",
        filters={"is_processed": 0, "employee": ["is", "set"]},
        fields=["name", "employee", "punch_time", "punch_type"])
    for log in logs:
        try:
            checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": log.employee,
                "time": log.punch_time, "log_type": "IN" if log.punch_type == "IN" else "OUT",
                "device_id": "Biometric"})
            checkin.insert(ignore_permissions=True)
            frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
        except frappe.DuplicateEntryError:
            frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
        except Exception as e:
            frappe.log_error(f"Checkin error {log.name}: {e}", "Biometric Sync")
    frappe.db.commit()


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
        checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": log.employee,
            "time": log.punch_time, "log_type": "IN" if log.punch_type == "IN" else "OUT",
            "device_id": "Biometric"})
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
# 8. PROCESS LOGS BY DATE RANGE
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_logs_by_date(start_date, end_date, employee=None, punch_type=None):
    try:
        filters = {"is_processed": 0, "employee": ["is", "set"],
            "punch_time": ["between", [start_date + " 00:00:00", end_date + " 23:59:59"]]}
        if employee:   filters["employee"]   = employee
        if punch_type: filters["punch_type"] = punch_type
        logs = frappe.get_all("Biometric attendance log", filters=filters,
            fields=["name", "employee", "punch_time", "punch_type"], limit=0)
        processed = failed = skipped = 0
        for log in logs:
            try:
                checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": log.employee,
                    "time": log.punch_time, "log_type": "IN" if log.punch_type == "IN" else "OUT",
                    "device_id": "Biometric"})
                checkin.insert(ignore_permissions=True)
                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                processed += 1
            except frappe.DuplicateEntryError:
                frappe.db.set_value("Biometric attendance log", log.name, "is_processed", 1)
                skipped += 1
            except Exception as e:
                frappe.log_error(f"Checkin error {log.name}: {e}", "Biometric Sync")
                failed += 1
        frappe.db.commit()
        return {"success": True, "processed": processed, "failed": failed, "skipped": skipped}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────
# 9. SYNC SELECTED MACHINES
#
# KEY FIX:
#   - `original_sync_time` is passed from JS (the last_sync_time BEFORE this sync run)
#   - All 5 batches use the SAME original_sync_time for filtering
#   - last_sync_time on the machine is only updated on the FINAL batch
#   - This means batches 2-5 filter from the same cutoff as batch 1 ✓
# ─────────────────────────────────────────────
@frappe.whitelist()
def sync_selected_machines(machine_names, auto_process=0, offset=0,
                            batch_num=1, total_batches=5, original_sync_time=None):
    import json
    if isinstance(machine_names, str):
        machine_names = json.loads(machine_names)

    offset           = int(offset or 0)
    batch_num        = int(batch_num or 1)
    total_batches    = int(total_batches or 5)
    is_final_batch   = (batch_num >= total_batches)
    EMIT_EVERY       = 5
    COMMIT_EVERY     = 50

    settings         = frappe.get_single("Biometric sync settings")
    fallback_days    = settings.default_fetch_days or 3
    sync_batch       = now_datetime().strftime("%Y-%m-%d %H:%M:%S")

    results = []

    for machine_name in machine_names:
        if not frappe.db.exists("Biometric machine", machine_name):
            results.append({"machine_id": machine_name, "machine": machine_name,
                            "status": "error", "error": "Machine not found"})
            continue

        machine_doc = frappe.get_doc("Biometric machine", machine_name)

        try:
            # ── Use original_sync_time for filtering on ALL batches ──
            # JS passes the last_sync_time it read BEFORE batch 1 started.
            # This guarantees all 5 batches filter from the same cutoff.
            filter_cutoff = original_sync_time if original_sync_time else machine_doc.last_sync_time

            raw      = fetch_from_machine(machine_doc)
            filtered = filter_new_records(raw, filter_cutoff, fallback_days)
            total    = len(filtered)

            # ── Equal batch slices ──
            batch_size  = math.ceil(total / total_batches) if total > 0 else 0
            batch_start = offset
            batch_end   = min(offset + batch_size, total)
            current     = filtered[batch_start:batch_end]
            this_size   = len(current)

            saved          = 0
            already_exists = 0
            pending_commit = 0
            invalid_ids    = []

            for idx, record in enumerate(current):
                punch_time = get_datetime(str(record.timestamp))
                emp_id     = str(record.user_id)

                emp = frappe.db.get_value("Employee", {"attendance_device_id": emp_id},
                                          ["name", "employee_name"], as_dict=True)
                if not emp:
                    if emp_id not in invalid_ids:
                        invalid_ids.append(emp_id)
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

                # Emit every EMIT_EVERY records for live counter
                if (idx + 1) % EMIT_EVERY == 0 or (idx + 1) == this_size:
                    frappe.publish_realtime(
                        event="biometric_fetch_progress",
                        message={
                            "machine_id":    machine_name,
                            "machine":       machine_doc.machine_name,
                            "batch_num":     batch_num,
                            "total_batches": total_batches,
                            "fetched":       idx + 1,
                            "batch_size":    this_size,
                            "saved":         saved,
                            "already_exists": already_exists,
                            "invalid_count": len(invalid_ids),
                            "status":        "running",
                        },
                        user=frappe.session.user
                    )

            if pending_commit > 0:
                frappe.db.commit()

            # ── Only update last_sync_time on the FINAL batch ──
            if is_final_batch:
                frappe.db.set_value("Biometric machine", machine_name, {
                    "last_sync_time":    sync_batch,
                    "connection_status": "Connected",
                })
                frappe.db.commit()
            else:
                # Still mark as connected
                frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Connected")
                frappe.db.commit()

            remaining_records = max(0, total - batch_end)
            remaining_batches = max(0, total_batches - batch_num)

            results.append({
                "machine":           machine_doc.machine_name,
                "machine_id":        machine_name,
                "status":            "ok",
                "total":             total,
                "batch_num":         batch_num,
                "total_batches":     total_batches,
                "batch_size":        this_size,
                "fetched":           this_size,
                "saved":             saved,
                "already_exists":    already_exists,
                "invalid_ids":       invalid_ids,
                "invalid_count":     len(invalid_ids),
                "remaining_records": remaining_records,
                "remaining_batches": remaining_batches,
                "next_offset":       batch_end   if remaining_records > 0 else None,
                "next_batch_num":    batch_num+1 if remaining_batches > 0 else None,
                # Return original_sync_time so JS can pass it back for next batch
                "original_sync_time": str(filter_cutoff) if filter_cutoff else None,
            })

        except Exception as e:
            frappe.db.set_value("Biometric machine", machine_name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {machine_doc.machine_name}: {e}", "Biometric Sync")
            results.append({"machine": machine_doc.machine_name, "machine_id": machine_name,
                            "status": "error", "error": str(e)})

    map_employees()
    if int(auto_process or 0):
        push_to_employee_checkin()

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
                frappe.get_doc({"doctype": "Biometric attendance log", "biometric_machine": m.name,
                    "device_emp_id": emp_id, "employee": emp.name, "employee_name": emp.employee_name,
                    "punch_time": punch_time, "punch_type": get_punch_type(record.punch),
                    "is_processed": 0, "sync_batch": sync_batch}).insert(ignore_permissions=True)
                saved += 1
            frappe.db.set_value("Biometric machine", m.name,
                {"last_sync_time": sync_batch, "connection_status": "Connected"})
            frappe.db.commit()
            results.append({"machine": m.machine_name, "total": len(filtered),
                "saved": saved, "already_exists": already_exists, "invalid_ids": invalid_ids, "status": "ok"})
        except Exception as e:
            frappe.db.set_value("Biometric machine", m.name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {m.machine_name}: {e}", "Biometric Sync")
            results.append({"machine": m.machine_name, "status": "error", "error": str(e)})
    map_employees()
    push_to_employee_checkin()
    return results


# ─────────────────────────────────────────────
# 11. DEBUG
# ─────────────────────────────────────────────
@frappe.whitelist()
def debug_fetch(machine_name):
    try:
        machine_doc   = frappe.get_doc("Biometric machine", machine_name)
        raw           = fetch_from_machine(machine_doc)
        settings      = frappe.get_single("Biometric sync settings")
        fallback_days = settings.default_fetch_days or 3
        filtered      = filter_new_records(raw, machine_doc.last_sync_time, fallback_days)
        return {"total_raw": len(raw), "total_filtered": len(filtered),
                "last_sync_time": str(machine_doc.last_sync_time), "fallback_days": fallback_days,
                "sample": [{"user_id": str(r.user_id), "timestamp": str(r.timestamp), "punch": r.punch}
                           for r in filtered[:5]]}
    except Exception as e:
        return {"error": str(e)}