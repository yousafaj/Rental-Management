// Copyright (c) 2025, osama.ahmed@deliverydevs.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("LOA", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {

            if (frm.doc.total_created_vehicle_cicpa < frm.doc.total_vehicle_quota) {
                frm.add_custom_button(__('Vehicle CICPA'), function() {
                    frappe.new_doc("CICPA", {
                        loa: frm.doc.name,
                        cicpa_type: "Vehicle"
                    });
                }, __("Create"));
            }

            if (frm.doc.total_created_driver_cicpa < frm.doc.total_driver_quota) {
                frm.add_custom_button(__('Driver CICPA'), function() {
                    frappe.new_doc("CICPA", {
                        loa: frm.doc.name,
                        cicpa_type: "Driver"
                    });
                }, __("Create"));
            }

        }
    },

    // Re-derive remaining_*_quota from total_*_quota minus already-allocated.
    // - On a brand-new (__islocal) LOA: allocated is 0, so remaining = total.
    // - On a saved Draft (docstatus=0): allow bumps; remaining = total - allocated.
    // - On a Submitted LOA (docstatus=1): refuse — server-side recalc owns this field
    //   and we don't want client edits to drift it.
    total_vehicle_quota: function(frm) {
        if (frm.doc.docstatus === 1) return;
        const allocated = frm.doc.allocated_vehicle_quota || 0;
        frm.set_value("remaining_vehicle_quota", Math.max(0, (frm.doc.total_vehicle_quota || 0) - allocated));
    },

    total_driver_quota: function(frm) {
        if (frm.doc.docstatus === 1) return;
        const allocated = frm.doc.allocated_driver_quota || 0;
        frm.set_value("remaining_driver_quota", Math.max(0, (frm.doc.total_driver_quota || 0) - allocated));
    }
});
