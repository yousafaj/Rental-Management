// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Driver", {
	employee(frm) {
		if (!frm.doc.employee) return;
		frappe.db.get_value("Employee", frm.doc.employee, "custom_nationality", (r) => {
			const value = r && (r.custom_nationality || r.nationality);
			if (!value) {
				// Fallback: try the standard Employee.nationality data field
				frappe.db.get_value("Employee", frm.doc.employee, "nationality", (r2) => {
					if (r2 && r2.nationality) {
						resolveNationality(frm, r2.nationality);
					}
				});
				return;
			}
			resolveNationality(frm, value);
		});
	}
});

function resolveNationality(frm, raw) {
	// If raw already matches a Nationality record name, use it directly.
	frappe.db.exists("Nationality", raw).then((exists) => {
		if (exists) {
			frm.set_value("nationality", raw);
			return;
		}
		// Otherwise try to match by nationality_name
		frappe.db.get_value("Nationality", { nationality_name: raw }, "name", (nat) => {
			if (nat && nat.name) {
				frm.set_value("nationality", nat.name);
			}
		});
	});
}
