import frappe
from frappe import _
from frappe.model.document import Document


class Loneinstallningar(Document):
	def validate(self):
		if not self.heltid_per_dag or self.heltid_per_dag <= 0 or self.heltid_per_dag > 24:
			frappe.throw(_("Heltid per dag måste vara större än 0 och högst 24 timmar."))
		for regel in self.tidsregler:
			if not 1 <= (regel.niva or 0) <= 5:
				frappe.throw(_("Tidsregel rad {0}: Nivå måste vara 1 till 5.").format(regel.idx))
			if not any(regel.get(f) for f in ("man", "tis", "ons", "tor", "fre", "lor", "son", "helgdag")):
				frappe.throw(_("Tidsregel rad {0}: välj minst en dag.").format(regel.idx))
