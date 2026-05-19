"""Rename the misspelled Driver custom field `custom_employement_type` → `custom_employment_type`.

Runs once on migrate. Idempotent: skips if the old field no longer exists.
"""
import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
    old = "custom_employement_type"
    new = "custom_employment_type"

    # Bail out if migration already applied
    if not frappe.db.exists("Custom Field", {"dt": "Driver", "fieldname": old}):
        return

    # Rename the Custom Field record + the underlying column on `tabDriver`
    try:
        rename_field("Driver", old, new)
        frappe.db.commit()
        # Drop cached Driver meta so subsequent reads see the new fieldname,
        # otherwise references to `doc.custom_employement_type` in still-warm
        # workers would silently resolve to None.
        frappe.clear_cache(doctype="Driver")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"rename_field Driver {old} -> {new} failed")
        raise
