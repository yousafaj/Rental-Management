import re

import frappe
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime


def autoname_asset(doc, method=None):
    """Build Asset name like ``ACC-ASS-2025-IT-000001``.

    Uses Frappe's `tabSeries` to atomically reserve the next 6-digit counter for the prefix.
    This is concurrency-safe (no race condition) and survives Asset deletions (counter
    never goes backwards, so we never reuse an already-issued name).
    """
    current_year = now_datetime().strftime("%Y")

    raw_ref = (getattr(doc, "custom_reference_number", "") or "").strip()
    if not raw_ref:
        frappe.throw("Please set Custom Reference Number before saving the Asset.")

    # Sanitize: make_autoname treats `.` as a separator and `#` as a digit placeholder.
    # Any of those inside the user-supplied ref would corrupt the counter series key.
    # Allow letters / digits / `_` / `-` only; collapse anything else to `_`.
    ref_no = re.sub(r"[^A-Za-z0-9_-]", "_", raw_ref)
    if not ref_no:
        frappe.throw("Custom Reference Number contains no valid characters (only letters, digits, '_', '-' allowed).")

    # `make_autoname` understands `.######` → reserves next 6-digit counter atomically.
    prefix = f"ACC-ASS-{current_year}-{ref_no}-"
    doc.name = make_autoname(prefix + ".######")
