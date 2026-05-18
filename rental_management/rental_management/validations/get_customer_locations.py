import frappe
from frappe import _


@frappe.whitelist()
def fetch_customer_locations_query(doctype, txt, searchfield, start, page_len, filters):
    customer_name = (filters or {}).get('customer_name')
    if not customer_name:
        return []

    # Permission check: only callers with read access to this Customer may enumerate its locations
    if not frappe.has_permission("Customer", "read", doc=customer_name):
        frappe.throw(_("Not permitted to read Customer {0}").format(customer_name), frappe.PermissionError)

    return frappe.db.sql(
        """
        SELECT location, location
        FROM `tabCustomer Locations cdt`
        WHERE parent = %s AND location LIKE %s
        LIMIT %s, %s
        """,
        (customer_name, f"%{txt or ''}%", start, page_len),
    )
