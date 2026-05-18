# Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DriverMovement(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		date: DF.Date
		driver: DF.Link
		employment_type: DF.Link | None
		mobilization_status: DF.Literal["", "Mobilize", "Demobilize"]
		ownership_status: DF.Data | None
		project: DF.Link
		shift: DF.Link
		vehicle: DF.Link
		vehicle_type: DF.Data | None
	# end: auto-generated types

	def on_submit(self):
		"""Minimal state maintenance: keep ``Driver.custom_state`` in sync.

		Mobilize → "With Client"; Demobilize → "Idle".
		Mirrors Vehicle Movement's server-side state tracking. The full shift-assignment
		state machine that previously lived here is intentionally gone.
		"""
		self._sync_driver_state(
			"With Client" if self.mobilization_status == "Mobilize" else "Idle"
		)

	def on_cancel(self):
		"""Reverse the state set on submit.

		A cancelled Mobilize → driver is no longer With Client → "Idle".
		A cancelled Demobilize → driver was set Idle by this movement → restore "With Client".
		"""
		self._sync_driver_state(
			"Idle" if self.mobilization_status == "Mobilize" else "With Client"
		)

	def _sync_driver_state(self, new_state: str):
		if not self.driver:
			return
		try:
			frappe.db.set_value("Driver", self.driver, "custom_state", new_state)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"DriverMovement {self.name}: failed to set Driver.custom_state={new_state}",
			)
			frappe.throw(_("Could not update Driver state for {0}").format(self.driver))
