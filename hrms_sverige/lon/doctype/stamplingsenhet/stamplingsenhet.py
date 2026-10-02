import secrets

import frappe
from frappe.model.document import Document
from frappe.utils import get_url


class Stamplingsenhet(Document):
	@frappe.whitelist()
	def skapa_nyckel(self) -> dict:
		"""Ny hemlig nyckel; bara hashen sparas och den gamla länken slutar fungera."""
		from hrms_sverige.lon.stampling import nyckel_hash

		self.check_permission("write")
		nyckel = secrets.token_urlsafe(32)
		self.db_set("nyckel_hash", nyckel_hash(nyckel))
		return {"nyckel": nyckel, "lank": get_url(f"/stampla?enhet={nyckel}")}
