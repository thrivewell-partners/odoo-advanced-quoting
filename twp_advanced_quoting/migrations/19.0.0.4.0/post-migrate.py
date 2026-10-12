from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """An install before M4 gets the Grouped style as each company's default, as a new one does."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    style = env.ref("twp_advanced_quoting.document_style_grouped", raise_if_not_found=False)
    if style:
        env["res.company"].search([("twp_default_document_style_id", "=", False)]).write(
            {"twp_default_document_style_id": style.id}
        )
