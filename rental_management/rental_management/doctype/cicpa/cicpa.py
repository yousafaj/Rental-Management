import frappe
from frappe import _
from frappe.model.document import Document

# Statuses that free up LOA quota (quota is recovered when a pass reaches one of these states)
RECOVERED_STATUSES = {"Lost", "Cancelled", "Expired"}


class CICPA(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		active: DF.Check
		amended_from: DF.Link | None
		cicpa_status: DF.Literal["", "Active", "Cancelled", "Expired", "Lost"]
		cicpa_type: DF.Literal["", "Driver", "Vehicle"]
		document: DF.Attach | None
		driver: DF.Link | None
		expiry_date: DF.Date
		issue_date: DF.Date
		loa: DF.Link
		vehicle: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.loa or not self.cicpa_type:
			return

		if self.cicpa_type == "Driver" and not self.driver:
			frappe.throw(_("A Driver must be selected when CICPA Type is set to Driver."))

		if self.cicpa_type == "Vehicle" and not self.vehicle:
			frappe.throw(_("A Vehicle must be selected when CICPA Type is set to Vehicle."))

		# One active CICPA per Driver / Vehicle.
		# Runs on every save (drafts AND submits) so two drafts can't both be submitted
		# for the same driver/vehicle.
		if self.cicpa_type == "Driver" and self.driver:
			existing = frappe.db.get_value(
				"CICPA",
				{
					"driver": self.driver,
					"cicpa_status": "Active",
					"docstatus": 1,
					"name": ["!=", self.name or ""],
				},
				"name",
			)
			if existing:
				frappe.throw(_(
					"Driver {0} already holds an active CICPA ({1}). "
					"Mark the existing pass as Lost, Cancelled, or Expired before issuing a new one."
				).format(self.driver, existing))

		if self.cicpa_type == "Vehicle" and self.vehicle:
			existing = frappe.db.get_value(
				"CICPA",
				{
					"vehicle": self.vehicle,
					"cicpa_status": "Active",
					"docstatus": 1,
					"name": ["!=", self.name or ""],
				},
				"name",
			)
			if existing:
				frappe.throw(_(
					"Vehicle {0} already holds an active CICPA ({1}). "
					"Mark the existing pass as Lost, Cancelled, or Expired before issuing a new one."
				).format(self.vehicle, existing))

		# Quota check only applies when creating a new record
		if not self.is_new():
			return

		loa_doc = frappe.get_doc("LOA", self.loa)

		# Recovered passes (Lost/Cancelled/Expired) free quota back, so only `remaining_*_quota` matters here.
		if self.cicpa_type == "Vehicle":
			if loa_doc.remaining_vehicle_quota <= 0:
				frappe.throw(_(
					"Vehicle quota for LOA {0} has been fully consumed. "
					"Recover an existing pass (Lost / Cancelled / Expired) or increase the LOA quota to proceed."
				).format(loa_doc.name))

		elif self.cicpa_type == "Driver":
			if loa_doc.remaining_driver_quota <= 0:
				frappe.throw(_(
					"Driver quota for LOA {0} has been fully consumed. "
					"Recover an existing pass (Lost / Cancelled / Expired) or increase the LOA quota to proceed."
				).format(loa_doc.name))

	def on_submit(self):
		if self.loa:
			try:
				loa_doc = frappe.get_doc("LOA", self.loa)

				if self.cicpa_type == "Vehicle":
					loa_doc.total_created_vehicle_cicpa = (loa_doc.total_created_vehicle_cicpa or 0) + 1

				elif self.cicpa_type == "Driver":
					loa_doc.total_created_driver_cicpa = (loa_doc.total_created_driver_cicpa or 0) + 1

				loa_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Error updating LOA CICPA count on submit")
				frappe.throw(_("Could not update the linked LOA. Details: {0}").format(str(e)))

			# Recompute allocated / remaining so the new Active CICPA consumes a slot immediately
			self._recalculate_loa_quota()

		if self.cicpa_type == "Driver" and self.driver:
			try:
				driver_doc = frappe.get_doc("Driver", self.driver)
				driver_doc.custom_has_cicpa = 1
				driver_doc.custom_cicpa = self.name
				existing_refs = [r.reference_no for r in driver_doc.get("custom_certification_list", [])]
				if self.name not in existing_refs:
					driver_doc.append("custom_certification_list", {
						"certification_name": "CICPA",
						"reference_no": self.name,
						"date_of_issue": self.issue_date,
						"date_of_expiry": self.expiry_date,
						"status": "Active",
					})
				driver_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "CICPA on_submit: Driver linkback failed")
				frappe.throw(_("Could not attach this CICPA to Driver {0}. Details: {1}").format(self.driver, str(e)))

		elif self.cicpa_type == "Vehicle" and self.vehicle:
			try:
				vehicle_doc = frappe.get_doc("Vehicle", self.vehicle)
				vehicle_doc.custom_has_cicpa = 1
				vehicle_doc.custom_cicpa = self.name
				existing_refs = [r.reference_no for r in vehicle_doc.get("custom_vehicle_certifications", [])]
				if self.name not in existing_refs:
					vehicle_doc.append("custom_vehicle_certifications", {
						"certification_name": "CICPA",
						"reference_no": self.name,
						"date_of_issue": self.issue_date,
						"date_of_expiry": self.expiry_date,
						"status": "Active",
					})
				vehicle_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "CICPA on_submit: Vehicle linkback failed")
				frappe.throw(_("Could not attach this CICPA to Vehicle {0}. Details: {1}").format(self.vehicle, str(e)))

	def on_update(self):
		"""Recalculate LOA quota whenever pass status changes.

		Changing a pass to Lost / Cancelled / Expired recovers its quota immediately.
		Each LOA is an independent record — quotas never transfer to another LOA.
		"""
		if not self.loa:
			return
		prev = self.get_doc_before_save()
		if prev and prev.cicpa_status != self.cicpa_status:
			self._recalculate_loa_quota()

	def _recalculate_loa_quota(self):
		"""Recompute LOA quota counters.

		Only Active CICPAs with a linked entity consume quota.
		Lost / Cancelled / Expired passes do not reduce remaining quota.
		"""
		if not self.loa:
			return
		try:
			loa_doc = frappe.get_doc("LOA", self.loa)

			if self.cicpa_type == "Vehicle":
				cicpa_list = frappe.get_all(
					"CICPA",
					filters={"loa": self.loa, "cicpa_type": "Vehicle", "docstatus": 1},
					fields=["name", "vehicle", "cicpa_status"],
				)
				allocated = sum(1 for d in cicpa_list if d.cicpa_status == "Active" and d.vehicle)
				recovered = sum(1 for d in cicpa_list if d.cicpa_status in RECOVERED_STATUSES)
				loa_doc.allocated_vehicle_quota = allocated
				loa_doc.total_cancelled_vehicle_cicpa = recovered
				loa_doc.remaining_vehicle_quota = loa_doc.total_vehicle_quota - allocated

			elif self.cicpa_type == "Driver":
				cicpa_list = frappe.get_all(
					"CICPA",
					filters={"loa": self.loa, "cicpa_type": "Driver", "docstatus": 1},
					fields=["name", "driver", "cicpa_status"],
				)
				allocated = sum(1 for d in cicpa_list if d.cicpa_status == "Active" and d.driver)
				recovered = sum(1 for d in cicpa_list if d.cicpa_status in RECOVERED_STATUSES)
				loa_doc.allocated_driver_quota = allocated
				loa_doc.total_cancelled_driver_cicpa = recovered
				loa_doc.remaining_driver_quota = loa_doc.total_driver_quota - allocated

			loa_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CICPA._recalculate_loa_quota failed")
			frappe.throw(_("Failed to recalculate LOA quota: {0}").format(str(e)))

	def _recover_quota_on_cancel(self):
		"""Free this CICPA's quota from the LOA before the LOA link is cleared."""
		try:
			loa_doc = frappe.get_doc("LOA", self.loa)

			if self.cicpa_type == "Vehicle":
				others = frappe.get_all(
					"CICPA",
					filters={
						"loa": self.loa,
						"cicpa_type": "Vehicle",
						"docstatus": 1,
						"name": ["!=", self.name],
					},
					fields=["name", "vehicle", "cicpa_status"],
				)
				allocated = sum(1 for d in others if d.cicpa_status == "Active" and d.vehicle)
				# +1 to count this record as recovered
				recovered = sum(1 for d in others if d.cicpa_status in RECOVERED_STATUSES) + 1
				loa_doc.allocated_vehicle_quota = allocated
				loa_doc.total_cancelled_vehicle_cicpa = recovered
				loa_doc.remaining_vehicle_quota = loa_doc.total_vehicle_quota - allocated

			elif self.cicpa_type == "Driver":
				others = frappe.get_all(
					"CICPA",
					filters={
						"loa": self.loa,
						"cicpa_type": "Driver",
						"docstatus": 1,
						"name": ["!=", self.name],
					},
					fields=["name", "driver", "cicpa_status"],
				)
				allocated = sum(1 for d in others if d.cicpa_status == "Active" and d.driver)
				recovered = sum(1 for d in others if d.cicpa_status in RECOVERED_STATUSES) + 1
				loa_doc.allocated_driver_quota = allocated
				loa_doc.total_cancelled_driver_cicpa = recovered
				loa_doc.remaining_driver_quota = loa_doc.total_driver_quota - allocated

			loa_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CICPA._recover_quota_on_cancel failed")
			frappe.throw(_("Failed to recover LOA quota on cancellation: {0}").format(str(e)))

	def on_trash(self):
		if self.loa:
			try:
				loa_doc = frappe.get_doc("LOA", self.loa)

				if self.cicpa_type == "Vehicle" and loa_doc.total_created_vehicle_cicpa:
					loa_doc.total_created_vehicle_cicpa = max(0, (loa_doc.total_created_vehicle_cicpa or 0) - 1)

				elif self.cicpa_type == "Driver" and loa_doc.total_created_driver_cicpa:
					loa_doc.total_created_driver_cicpa = max(0, (loa_doc.total_created_driver_cicpa or 0) - 1)

				loa_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Error updating LOA CICPA count on delete")
				frappe.throw(_("Failed to update LOA record during deletion: {0}").format(str(e)))

	def on_change(self):
		if self.cicpa_type == "Vehicle" and self.vehicle:
			try:
				vehicle_doc = frappe.get_doc("Vehicle", self.vehicle)
				updated = False

				for row in vehicle_doc.get("custom_vehicle_certifications", []):
					if row.certification_name == "CICPA" and row.reference_no == self.name:
						row.date_of_expiry = self.expiry_date
						updated = True
						break

				if updated:
					vehicle_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Error updating CICPA expiry date in Vehicle")
				frappe.throw(_("Failed to update CICPA expiry date in Vehicle: {0}").format(str(e)))

		if self.cicpa_type == "Driver" and self.driver:
			try:
				driver_doc = frappe.get_doc("Driver", self.driver)
				updated = False

				for row in driver_doc.get("custom_certification_list", []):
					if row.certification_name == "CICPA" and row.reference_no == self.name:
						row.date_of_expiry = self.expiry_date
						updated = True
						break

				if updated:
					driver_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Error updating CICPA expiry date in Driver")
				frappe.throw(_("Failed to update CICPA expiry date in Driver: {0}").format(str(e)))

	def before_cancel(self):
		# Recover quota BEFORE clearing the LOA link so the recalculation can still resolve the LOA
		if self.loa:
			self._recover_quota_on_cancel()
			self.db_set("loa", None, update_modified=False)

		try:
			cicpa_logs = frappe.get_all(
				"CICPA Logs",
				filters={"cicpa": self.name},
				fields=["name", "docstatus"],
			)

			for log in cicpa_logs:
				frappe.db.set_value("CICPA Logs", log.name, "cicpa", None)

				log_doc = frappe.get_doc("CICPA Logs", log.name)
				if log_doc.docstatus == 1:
					log_doc.cancel()

				log_doc.delete(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CICPA before_cancel: CICPA Logs cleanup failed")
			frappe.throw(_("Cannot cancel CICPA due to linked CICPA Logs: {0}").format(str(e)))

		if self.cicpa_type == "Vehicle" and self.vehicle:
			try:
				vehicle_doc = frappe.get_doc("Vehicle", self.vehicle)

				vehicle_doc.custom_has_cicpa = 0
				vehicle_doc.custom_cicpa = None
				vehicle_doc.custom_vehicle_certifications = [
					row for row in vehicle_doc.get("custom_vehicle_certifications", [])
					if not (row.certification_name == "CICPA" and row.reference_no == self.name)
				]

				vehicle_doc.save(ignore_permissions=True)
				self.db_set("vehicle", None, update_modified=False)

			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "CICPA before_cancel: Vehicle cleanup failed")
				frappe.throw(_("Failed to clean CICPA from Vehicle: {0}").format(str(e)))

		if self.cicpa_type == "Driver" and self.driver:
			try:
				driver_doc = frappe.get_doc("Driver", self.driver)

				driver_doc.custom_has_cicpa = 0
				driver_doc.custom_cicpa = None
				driver_doc.custom_certification_list = [
					row for row in driver_doc.get("custom_certification_list", [])
					if not (row.certification_name == "CICPA" and row.reference_no == self.name)
				]

				driver_doc.save(ignore_permissions=True)
				self.db_set("driver", None, update_modified=False)

			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "CICPA before_cancel: Driver cleanup failed")
				frappe.throw(_("Failed to clean CICPA from Driver: {0}").format(str(e)))


@frappe.whitelist()
def mark_pass_status(name: str, new_status: str):
	"""Change a CICPA's pass status (Active / Lost / Cancelled / Expired) and recover quota.

	Use this from custom buttons / API instead of `frappe.db.set_value`, since
	submitted-doc status changes via db_set bypass on_update and leave LOA counters stale.
	"""
	allowed = {"Active", "Lost", "Cancelled", "Expired"}
	if new_status not in allowed:
		frappe.throw(_("Invalid pass status: {0}").format(new_status))

	cicpa = frappe.get_doc("CICPA", name)

	if cicpa.docstatus != 1:
		frappe.throw(_(
			"Pass status can only be changed on submitted CICPAs. "
			"This document is in {0} state."
		).format({0: "Draft", 2: "Cancelled"}.get(cicpa.docstatus, "Unknown")))

	old_status = cicpa.cicpa_status
	if old_status == new_status:
		return

	# Reactivating a recovered pass must respect remaining quota
	if new_status == "Active" and old_status in RECOVERED_STATUSES and cicpa.loa:
		loa_doc = frappe.get_doc("LOA", cicpa.loa)
		if cicpa.cicpa_type == "Vehicle" and (loa_doc.remaining_vehicle_quota or 0) <= 0:
			frappe.throw(_(
				"Cannot reactivate this pass: Vehicle quota for LOA {0} is fully consumed."
			).format(loa_doc.name))
		if cicpa.cicpa_type == "Driver" and (loa_doc.remaining_driver_quota or 0) <= 0:
			frappe.throw(_(
				"Cannot reactivate this pass: Driver quota for LOA {0} is fully consumed."
			).format(loa_doc.name))

	# Persist the new status. db_set is required for submitted docs (docstatus=1).
	cicpa.db_set("cicpa_status", new_status, update_modified=True)
	if new_status in RECOVERED_STATUSES:
		cicpa.db_set("active", 0, update_modified=False)
	elif new_status == "Active":
		cicpa.db_set("active", 1, update_modified=False)

	# Re-read so the recalculation uses the latest persisted status
	cicpa.reload()
	cicpa._recalculate_loa_quota()

	# Audit trail
	frappe.get_doc({
		"doctype": "CICPA Logs",
		"cicpa": cicpa.name,
		"loa": cicpa.loa,
		"vehicle": cicpa.vehicle,
		"driver": cicpa.driver,
		"remarks": f"Status changed: {old_status} → {new_status}",
		"docstatus": 1,
	}).insert(ignore_permissions=True)

	return {"name": cicpa.name, "cicpa_status": new_status}
