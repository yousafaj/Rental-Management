// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Movement", {

    vehicle(frm) {
        if (frm.doc.vehicle) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Vehicle",
                    filters: { name: frm.doc.vehicle },
                    fieldname: "custom_project"
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("project_id", r.message.custom_project);
                    }
                }
            });
        }
        else {
            frm.set_value("project_id", null);
        }
    },

    // Note: vehicle dropdown is intentionally unfiltered. Previous filters on
    // custom_state / custom_status broke once those fields were hidden and
    // stopped being user-maintained. Users now pick any Vehicle and the
    // server-side logic in vehicle_movement.py keeps custom_state correct.
});
