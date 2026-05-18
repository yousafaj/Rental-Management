import frappe
from frappe.utils import nowdate, getdate

# Recovered statuses are tracked alongside cicpa.py — duplicated here to avoid
# importing across the doctype boundary in a scheduled task.
RECOVERED_STATUSES = {"Lost", "Cancelled", "Expired"}


def daily():
    validate_vehicle()


def validate_vehicle():
    """Deactivate Vehicles whose underlying Asset was Sold or whose rent has ended.

    When a Vehicle goes Inactive we also free up any Active CICPA linked to it —
    otherwise that LOA slot stays consumed forever even though no live Vehicle uses it.

    Both filter and target use `custom_status` — the standard Vehicle doctype has no `status` field.
    """
    vehicles = frappe.get_all(
        "Vehicle",
        filters={"custom_status": "Active"},
        fields=["name", "custom_vehicle_type", "custom_asset_mapping", "custom_rent_end_date"],
    )

    today = getdate(nowdate())

    for v in vehicles:
        try:
            should_deactivate = False

            if v.custom_vehicle_type == "Owned" and v.custom_asset_mapping:
                asset_status = frappe.db.get_value("Asset", v.custom_asset_mapping, "status")
                if asset_status == "Sold":
                    should_deactivate = True

            elif v.custom_vehicle_type == "Rented" and v.custom_rent_end_date:
                rent_end = getdate(v.custom_rent_end_date)
                if rent_end < today:
                    should_deactivate = True

            if should_deactivate:
                frappe.db.set_value("Vehicle", v.name, "custom_status", "Inactive")
                _recover_quota_for_vehicle(v.name)

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"daily.validate_vehicle failed for {v.name}")

    frappe.db.commit()


def _recover_quota_for_vehicle(vehicle_name: str):
    """Expire any Active CICPA tied to this Vehicle and recompute its LOA quota.

    Uses status "Expired" because the cause is end-of-life of the vehicle (rental ended
    or asset sold), not a manual cancellation. "Expired" is one of RECOVERED_STATUSES,
    so the LOA quota is freed immediately.
    """
    active_passes = frappe.get_all(
        "CICPA",
        filters={
            "vehicle": vehicle_name,
            "docstatus": 1,
            "cicpa_status": "Active",
        },
        fields=["name", "loa", "cicpa_type"],
    )

    if not active_passes:
        return

    affected_loas = set()
    for pass_row in active_passes:
        frappe.db.set_value("CICPA", pass_row.name, "cicpa_status", "Expired", update_modified=True)
        frappe.db.set_value("CICPA", pass_row.name, "active", 0, update_modified=False)
        if pass_row.loa:
            affected_loas.add(pass_row.loa)

        # Audit trail so it's clear *why* this pass changed without a user action
        try:
            frappe.get_doc({
                "doctype": "CICPA Logs",
                "cicpa": pass_row.name,
                "loa": pass_row.loa,
                "vehicle": vehicle_name,
                "remarks": "Auto-expired by daily job: linked Vehicle was deactivated",
                "docstatus": 1,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"daily: CICPA Logs audit insert failed for {pass_row.name}")

    # Recompute each affected LOA's quota counters
    for loa_name in affected_loas:
        try:
            _recompute_loa_quota(loa_name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"daily: LOA quota recompute failed for {loa_name}")


def _recompute_loa_quota(loa_name: str):
    """Recompute Vehicle quota counters for an LOA. Mirrors cicpa._recalculate_loa_quota.

    Kept local so the daily task is self-contained and can't be affected by
    permission-aware code paths in the doctype controller.
    """
    cicpa_list = frappe.get_all(
        "CICPA",
        filters={"loa": loa_name, "cicpa_type": "Vehicle", "docstatus": 1},
        fields=["name", "vehicle", "cicpa_status"],
    )
    allocated = sum(1 for d in cicpa_list if d.cicpa_status == "Active" and d.vehicle)
    recovered = sum(1 for d in cicpa_list if d.cicpa_status in RECOVERED_STATUSES)

    loa_doc = frappe.get_doc("LOA", loa_name)
    loa_doc.allocated_vehicle_quota = allocated
    loa_doc.total_cancelled_vehicle_cicpa = recovered
    loa_doc.remaining_vehicle_quota = (loa_doc.total_vehicle_quota or 0) - allocated
    loa_doc.save(ignore_permissions=True)
