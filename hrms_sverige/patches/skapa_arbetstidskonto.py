from hrms_sverige.setup.leave import ARBETSTIDSKONTO, ensure_leave_types, ensure_paxml_tidkoder


def execute():
	"""Frånvarotypen Arbetstidskonto (PAXml ATK) på befintliga siter. Andra typer som HR tagit bort
	återskapas inte."""
	ensure_leave_types([ARBETSTIDSKONTO])
	ensure_paxml_tidkoder()
