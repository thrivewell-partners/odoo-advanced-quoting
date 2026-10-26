from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The company report stylesheet is rebuilt with the options' colours in it.

    Odoo rebuilds it only when a company's Document Layout changes.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.company"]._update_asset_style()
