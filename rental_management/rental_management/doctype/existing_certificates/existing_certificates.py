# Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExistingCertificates(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		certificate_name: DF.Data | None
		customer: DF.Link | None
		date_of_expiry: DF.Date | None
		date_of_issue: DF.Date | None
		driver: DF.Link | None
		employee: DF.Data | None
		mark_as_not_renew: DF.Check
		reference_no: DF.Data | None
		row_name: DF.Data | None
		vehicle: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.row_name or not self.date_of_expiry:
			return

		prev = self.get_doc_before_save()
		if not prev or self.date_of_expiry == prev.date_of_expiry:
			return

		# Map this record onto the child row of its parent.
		# IMPORTANT: do NOT call parent_doc.save() — the parent's own validate
		# would re-sync Existing Certificates and recurse into this validate again.
		# Update the child row directly via frappe.db.set_value.
		child_doctype = None
		if self.vehicle:
			child_doctype = "Vehicle cdt"
		elif self.customer:
			child_doctype = "Customer cdt"
		elif self.driver:
			child_doctype = "Driver cdt"

		if child_doctype:
			try:
				frappe.db.set_value(
					child_doctype,
					self.row_name,
					"date_of_expiry",
					self.date_of_expiry,
					update_modified=False,
				)
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					f"ExistingCertificates {self.name}: failed to sync child row {self.row_name}",
				)

		if self.certificate_name == "CICPA" and self.reference_no:
			try:
				frappe.db.set_value("CICPA", self.reference_no, "expiry_date", self.date_of_expiry)
			except frappe.DoesNotExistError:
				frappe.throw(f"CICPA document '{self.reference_no}' not found.")