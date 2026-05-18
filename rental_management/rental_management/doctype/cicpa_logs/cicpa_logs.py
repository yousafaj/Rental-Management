# Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CICPALogs(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		cicpa: DF.Data | None
		driver: DF.Link | None
		loa: DF.Link | None
		remarks: DF.Text | None
		vehicle: DF.Link | None
	# end: auto-generated types

	def on_update(self):
		"""Auto-cancel and delete this log when its CICPA link is cleared.

		Guarded by `frappe.flags.in_cicpa_log_cleanup` so we don't recurse when
		`CICPA.before_cancel` is already iterating these logs. The flag is reset
		in `finally` to avoid leaking across requests in the same worker.
		"""
		if self.cicpa:
			return

		if frappe.flags.in_cicpa_log_cleanup:
			return

		frappe.flags.in_cicpa_log_cleanup = True
		try:
			doc = frappe.get_doc(self.doctype, self.name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				doc.cancel()
			try:
				doc.delete(ignore_permissions=True)
			except frappe.DoesNotExistError:
				pass
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CICPA Logs auto cleanup failed")
			frappe.throw(_("Failed to auto-delete CICPA Log: {0}").format(str(e)))
		finally:
			frappe.flags.in_cicpa_log_cleanup = False
