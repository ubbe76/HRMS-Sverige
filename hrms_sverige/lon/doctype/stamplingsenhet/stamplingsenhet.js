frappe.ui.form.on("Stamplingsenhet", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Skapa länk"), () =>
			frappe.confirm(__("En ny länk gör den gamla ogiltig. Fortsätta?"), () =>
				frm.call("skapa_nyckel").then((r) => {
					frappe.msgprint({
						title: __("Länk till stämplingssidan"),
						message:
							__("Öppna länken en gång på enheten. Den visas bara nu.") +
							`<p><input class="form-control" readonly value="${r.message.lank}" onclick="this.select()"></p>`,
					});
					frm.reload_doc();
				})
			)
		);
	},
});
