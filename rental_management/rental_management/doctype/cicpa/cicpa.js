// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("CICPA", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			const status = frm.doc.cicpa_status;
			const add_btn = (label, new_status) => {
				frm.add_custom_button(label, () => {
					frappe.confirm(
						`Change CICPA status to <b>${new_status}</b>?`,
						() => {
							frappe.call({
								method: "rental_management.rental_management.doctype.cicpa.cicpa.mark_pass_status",
								args: { name: frm.doc.name, new_status: new_status },
								callback: () => frm.reload_doc()
							});
						}
					);
				}, __("Change Status"));
			};

			if (status !== "Lost")      add_btn(__("Mark as Lost"), "Lost");
			if (status !== "Cancelled") add_btn(__("Mark as Cancelled"), "Cancelled");
			if (status !== "Expired")   add_btn(__("Mark as Expired"), "Expired");
			if (status !== "Active")    add_btn(__("Mark as Active"), "Active");
		}
	},

	// `before_cancel` is the right place for a confirmation dialog —
	// `after_cancel` fires AFTER the doc is already cancelled.
	// CICPA Logs cleanup happens server-side in Python (before_cancel hook),
	// so no client-side cleanup is needed.
	before_cancel(frm) {
		return new Promise((resolve, reject) => {
			frappe.confirm(
				__("Cancelling this CICPA will also delete all of its linked CICPA Logs and recover quota. Do you want to proceed?"),
				() => resolve(),
				() => {
					frappe.show_alert({ message: __("Cancellation aborted."), indicator: "blue" });
					reject();
				}
			);
		});
	}
});
