frappe.ui.form.on("Loneunderlag", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.ar) {
			const forra = moment().subtract(1, "month");
			frm.set_value("ar", forra.year());
			frm.set_value("manad", frm.fields_dict.manad.df.options.split("\n")[forra.month()]);
		}
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Hämta frånvaro och tid"), () =>
				frm
					.call({
						doc: frm.doc,
						method: "hamta_franvaro",
						freeze: true,
						freeze_message: __("Hämtar frånvaro och tid …"),
					})
					.then(() => frm.reload_doc())
			);
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Ladda ner PAXml"), () =>
				window.open(
					"/api/method/hrms_sverige.lon.doctype.loneunderlag.loneunderlag.ladda_ner?name=" +
						encodeURIComponent(frm.doc.name)
				)
			).addClass("btn-primary");
		}
	},
});
