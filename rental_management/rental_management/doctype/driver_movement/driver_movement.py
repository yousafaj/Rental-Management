# Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
# For license information, please see license.txt

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
	pass
