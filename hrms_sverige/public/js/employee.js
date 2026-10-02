frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (
			frm.is_new() ||
			!(frappe.user.has_role("HR Manager") || frappe.user.has_role("HR User"))
		)
			return;
		frm.add_custom_button(
			__("Sätt PIN"),
			() => {
				const d = new frappe.ui.Dialog({
					title: __("PIN-kod för stämpling"),
					fields: [
						{
							fieldname: "pin",
							fieldtype: "Password",
							label: __("Ny PIN-kod (4 till 6 siffror)"),
							reqd: 1,
						},
					],
					primary_action_label: __("Spara"),
					primary_action(values) {
						frappe
							.call("hrms_sverige.lon.stampling.satt_pin", {
								employee: frm.doc.name,
								pin: values.pin,
							})
							.then(() => {
								d.hide();
								frappe.show_alert({
									message: __(
										"PIN-koden är satt. Den anställde byter den vid första stämplingen."
									),
									indicator: "green",
								});
								frm.reload_doc();
							});
					},
				});
				d.show();
			},
			__("Stämpling")
		);
	},
});
