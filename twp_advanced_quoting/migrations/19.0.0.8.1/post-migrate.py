from odoo import SUPERUSER_ID, api
from odoo.addons.twp_advanced_quoting import rebuild_company_styles


def migrate(cr, version):
    """The company report stylesheet is rebuilt with the options' colours in it.

    19.0.0.8.0 asked for it without naming the module, so Odoo rendered it without the module's
    own view and the stylesheet stayed as it was.
    """
    if not version:
        return
    rebuild_company_styles(api.Environment(cr, SUPERUSER_ID, {}))
