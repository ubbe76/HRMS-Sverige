"""Dölj oanvända HRMS-delar även i Apps-lägets meny (frappe 16.51+)."""

from hrms_sverige.setup.workspaces import hide_in_dock


def execute():
	hide_in_dock()
