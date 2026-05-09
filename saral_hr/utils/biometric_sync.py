import frappe
from frappe.utils import now_datetime, get_datetime, add_days
from frappe.utils.password import get_decrypted_password


def get_machine_password(machine_name):
    """
    Fetch and decrypt the password from Frappe's encrypted password storage.
    Returns 0 if no password is set or if it's not a valid integer.
    """
    try:
        raw = get_decrypted_password("Biometric machine", machine_name, "device_password")
        return int(raw) if raw else 0
    except (ValueError, TypeError):
        return 0
    except Exception:
        return 0


# ─────────────────────────────────────────────
# 1. TEST CONNECTION  (called from button)
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
# 2. FETCH FROM ONE MACHINE  (read-only)
# ─────────────────────────────────────────────
def fetch_from_machine(machine_doc):
    """
    Fetch attendance logs from a single biometric machine.
    ONLY reads data — never writes to or modifies the device.
    """
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
        attendance = conn.get_attendance()   # READ ONLY — does not modify device
        return attendance
    finally:
        conn.enable_device()
        conn.disconnect()


# ─────────────────────────────────────────────
# 3. FILTER: ONLY NEW DATA AFTER LAST SYNC
# ─────────────────────────────────────────────
def filter_new_records(attendance_list, last_sync_time, fallback_days=3):
    """
    Returns only records after last_sync_time.
    If last_sync_time is None, returns last fallback_days days.
    """
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
    """Map ZKTeco punch code to IN / OUT / Unknown."""
    mapping = {0: "IN", 1: "OUT", 4: "IN", 5: "OUT"}
    return mapping.get(punch_code, "Unknown")


# ─────────────────────────────────────────────
# 5. SAVE RAW LOGS (skip duplicates)
# ─────────────────────────────────────────────
def save_raw_logs(machine_name, records, sync_batch):
    """
    Insert new Biometric Attendance Log records.
    Skips any punch already saved (deduplication).
    """
    saved = 0
    for record in records:
        punch_time = get_datetime(str(record.timestamp))

        # Deduplication check
        exists = frappe.db.exists("Biometric attendance log", {
            "biometric_machine": machine_name,
            "device_emp_id": str(record.user_id),
            "punch_time": punch_time,
        })
        if exists:
            continue

        # Map employee at insert time
        emp = frappe.db.get_value(
            "Employee",
            {"attendance_device_id": str(record.user_id)},
            ["name", "employee"],
            as_dict=True,
        )

        log = frappe.get_doc({
            "doctype": "Biometric attendance log",
            "biometric_machine": machine_name,
            "device_emp_id": str(record.user_id),
            "employee": emp.name if emp else None,
            "employee_name": emp.employee if emp else None,
            "punch_time": punch_time,
            "punch_type": get_punch_type(record.punch),
            "is_processed": 0,
            "sync_batch": sync_batch,
        })
        log.insert(ignore_permissions=True)
        saved += 1

    frappe.db.commit()
    return saved


# ─────────────────────────────────────────────
# 6. MAP DEVICE EMP ID → FRAPPE EMPLOYEE
# ─────────────────────────────────────────────
def map_employees():
    """
    Match device_emp_id to Frappe Employee using
    the attendance_device_id field on Employee.
    """
    unlinked = frappe.get_all(
        "Biometric attendance log",
        filters={"employee": ["is", "not set"], "is_processed": 0},
        fields=["name", "device_emp_id"],
    )
    for log in unlinked:
        emp = frappe.db.get_value(
            "Employee",
            {"attendance_device_id": log.device_emp_id},
            ["name", "employee"],
            as_dict=True,
        )
        if emp:
            frappe.db.set_value("Biometric attendance log", log.name, {
                "employee": emp.name,
                "employee_name": emp.employee,
            })

    frappe.db.commit()


# ─────────────────────────────────────────────
# 7. CREATE EMPLOYEE CHECKIN (optional auto-process)
# ─────────────────────────────────────────────
def push_to_employee_checkin():
    """
    Push unprocessed logs to ERPNext Employee Checkin doctype.
    Only runs if Auto Process to Checkin is enabled in settings.
    """
    settings = frappe.get_single("Biometric sync settings")
    if not settings.auto_process_to_checkin:
        return

    logs = frappe.get_all(
        "Biometric attendance log",
        filters={"is_processed": 0, "employee": ["is", "set"]},
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
    """
    Main entry point. Called by scheduler or manually via button.
    Loops all active Biometric Machines.
    """
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
            # Fetch all records from device (read-only)
            raw = fetch_from_machine(machine_doc)

            # Filter: only records after last sync
            filtered = filter_new_records(raw, m.last_sync_time, fallback_days)

            # Save raw logs
            saved = save_raw_logs(m.name, filtered, sync_batch)

            # Update last sync time and status
            frappe.db.set_value("Biometric machine", m.name, {
                "last_sync_time": sync_batch,
                "connection_status": "Connected",
            })
            frappe.db.commit()

            results.append({
                "machine": m.machine_name,
                "fetched": len(filtered),
                "saved": saved,
                "status": "ok",
            })
            frappe.logger().info(f"Biometric sync: {m.machine_name} → {saved} new records")

        except Exception as e:
            frappe.db.set_value("Biometric machine", m.name, "connection_status", "Failed")
            frappe.db.commit()
            frappe.log_error(f"Machine {m.machine_name}: {e}", "Biometric Sync")
            results.append({
                "machine": m.machine_name,
                "status": "error",
                "error": str(e),
            })

    # Map employees and push to checkin
    map_employees()
    push_to_employee_checkin()

    return results


# ─────────────────────────────────────────────
# 9. PROCESS SINGLE LOG (called from form button)
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_single_log(log_name):
    """Process a single Biometric Attendance Log to Employee Checkin."""
    try:
        log = frappe.get_doc("Biometric attendance log", log_name)

        if not log.employee:
            return {"success": False, "message": "No employee mapped to this log"}

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
# 10. PROCESS LOGS BY DATE RANGE (called from list view button)
# ─────────────────────────────────────────────
@frappe.whitelist()
def process_logs_by_date(start_date, end_date, employee=None, punch_type=None):
    """
    Process Biometric Attendance Logs to Employee Checkin
    filtered by date range, employee, and punch type.
    """
    try:
        filters = {
            "is_processed": 0,
            "employee": ["is", "set"],
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