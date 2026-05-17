// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt
//
// Auto-fetch nationality from the linked Employee when an Employee is selected
// on the Driver form.
//
// The Driver form displays `custom_nationality` (a Link to the Nationality
// doctype). The standard Driver doctype has no `nationality` field — writing
// to it raises "Field nationality not found".
//
// The Employee doctype typically has a `nationality` field (Link to Country
// in stock ERPNext, sometimes a Data or custom Link in customised installs).
// We try a few resolution strategies to map whatever the Employee stores into
// a valid Nationality record name.

frappe.ui.form.on("Driver", {
	employee(frm) {
		if (!frm.doc.employee) return;

		// Pull both possible Employee fields in one round trip
		frappe.db.get_value(
			"Employee",
			frm.doc.employee,
			["nationality", "custom_nationality"],
			(r) => {
				if (!r) return;
				const raw = r.custom_nationality || r.nationality;
				if (!raw) return;
				resolveNationality(frm, raw);
			}
		);
	}
});

function resolveNationality(frm, raw) {
	if (!frm.fields_dict.custom_nationality) {
		// Defensive: form schema doesn't include the field. Bail silently.
		return;
	}

	// 1) Exact match on Nationality record name
	frappe.db.exists("Nationality", raw).then((exists) => {
		if (exists) {
			frm.set_value("custom_nationality", raw);
			return;
		}

		// 2) Match by the `nationality_name` field (case-sensitive)
		frappe.db.get_value(
			"Nationality",
			{ nationality_name: raw },
			"name",
			(nat) => {
				if (nat && nat.name) {
					frm.set_value("custom_nationality", nat.name);
					return;
				}

				// 3) Case-insensitive fuzzy match — handles "INDIA" vs "India"
				frappe.db.get_list("Nationality", {
					filters: [["nationality_name", "like", raw]],
					fields: ["name"],
					limit: 1,
				}).then((rows) => {
					if (rows && rows.length) {
						frm.set_value("custom_nationality", rows[0].name);
					}
				});
			}
		);
	});
}
