from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route

from odoo.addons.sale.controllers import portal


class CustomerPortal(portal.CustomerPortal):

    @route(["/my/orders/<int:order_id>/twp_option"], type="jsonrpc", auth="public", website=True)
    def twp_portal_option_choose(self, order_id, line_id, chosen, access_token=None, **kwargs):
        """The customer chooses an alternative, or adds or removes an add-on, on the online quote.

        Built like Sales' own route for optional lines: the access token opens the order, and
        everything else is the order's to refuse (see SaleOrder._twp_choose_online).
        """
        try:
            order_sudo = self._document_check_access("sale.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {"error": "invalid"}
        try:
            section = order_sudo.order_line.browse(int(line_id)).exists()
        except (TypeError, ValueError):
            return {"error": "invalid"}
        user = request.env.user
        partner = order_sudo.partner_id if user._is_public() else user.partner_id
        if not section or not order_sudo._twp_choose_online(section, bool(chosen), partner):
            return {"error": "refused"}
        return {"success": True}
