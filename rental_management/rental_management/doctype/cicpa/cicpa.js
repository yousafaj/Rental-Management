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

	after_cancel(frm) {
		frappe.confirm(
			"Cancelling this CICPA will also delete all of its linked CICPA Logs. Do you want to proceed?",
			function () {
				// Proceed with cancellation
				frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "CICPA Logs",
						filters: {
							cicpa: frm.doc.name
						},
						fields: ["name"]
					},
					callback: function (r) {
						if (r.message) {
							r.message.forEach(log => {
								frappe.call({
									method: "frappe.client.delete",
									args: {
										doctype: "CICPA Logs",
										name: log.name
									},
									callback: function () {
										console.log("Deleted log:", log.name);
									}
								});
							});
						}
					}
				});
				// let cancel continue
				frm.script_manager.trigger("cancel");
			},
			function () {
				// If user declines confirmation, abort cancellation
				frappe.msgprint(__("Cancellation was not confirmed. The CICPA remains active."));
			}
		);

		// Prevent default cancel until user confirms
		return false;
	}
});
