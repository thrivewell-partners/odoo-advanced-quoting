from odoo import SUPERUSER_ID, api
from odoo.addons.twp_advanced_quoting import rebuild_company_styles


def migrate(cr, version):
    """The company report stylesheet is rebuilt with the compact layout's colours in it.

    19.0.0.10.0 added them to the stylesheet's view without rebuilding it.
    """
    if not version:
        return
    rebuild_company_styles(api.Environment(cr, SUPERUSER_ID, {}))
