from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TwpBidCopy(models.TransientModel):
    """One bid copied to several bidders, each copy with its own number and the bid's prices."""

    _name = "twp.bid.copy"
    _description = "Copy a bid to customers"

    bid_id = fields.Many2one("sale.order", string="Bid", required=True, readonly=True)
    partner_ids = fields.Many2many("res.partner", string="Customers", required=True)
    already_bid_ids = fields.Many2many(
        "res.partner", string="Already Bid To", compute="_compute_already_bid_ids",
        help="Customers with an open bid on the same opportunity.",
    )

    @api.depends("bid_id")
    def _compute_already_bid_ids(self):
        for wizard in self:
            bids = wizard.bid_id | wizard.bid_id._twp_competing_bids()
            wizard.already_bid_ids = bids.partner_id

    def action_apply(self):
        self.ensure_one()
        bid = self.bid_id
        if not bid.twp_is_bid:
            raise UserError(_("%s is no longer a bid, so it can't be copied to other bidders.", bid.name))
        copies = self.env["sale.order"]
        for partner in self.partner_ids:
            copies |= bid._twp_copy_for(partner)
        bid.message_post(body=_("Copied to %s.", ", ".join(copies.mapped(lambda c: f"{c.partner_id.name} ({c.name})"))))
        if len(copies) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "res_id": copies.id,
                "views": [(self.env.ref("sale.view_order_form").id, "form")],
            }
        action = self.env["ir.actions.actions"]._for_xml_id("twp_bids.action_bids")
        action["domain"] = [("id", "in", copies.ids)]
        return action
