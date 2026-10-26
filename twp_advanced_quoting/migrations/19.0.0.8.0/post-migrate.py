from odoo import SUPERUSER_ID, api
from odoo.addons.twp_advanced_quoting import rebuild_company_styles


def migrate(cr, version):
    """The company report stylesheet is rebuilt with the options' colours in it."""
    if not version:
        return
    rebuild_company_styles(api.Environment(cr, SUPERUSER_ID, {}))
