from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TwpBidCopy(models.TransientModel):
    """One bid copied to several bidders, each copy with its own number and the bid's prices."""

    _name = "twp.bid.copy"
    _description = "Duplicate a bid for contractors"

    bid_id = fields.Many2one(
        "sale.order", string="Bid", required=True, domain=[("twp_is_bid", "=", True)],
        help="The bid to copy. From a project it can be a bid on any project.",
    )
    partner_ids = fields.Many2many("res.partner", string="Contractors", required=True)
    opportunity_id = fields.Many2one(
        "crm.lead", string="Project", compute="_compute_opportunity_id", store=True, readonly=False,
        domain=[("type", "=", "opportunity")],
        help="The opportunity the copies are bids on. Another one makes them bids for that job, "
             "which don't compete with this bid.",
    )
    already_bid_ids = fields.Many2many(
        "res.partner", string="Already Bid To", compute="_compute_already_bid_ids",
        help="Contractors with an open bid on the project.",
    )

    @api.depends("bid_id")
    def _compute_opportunity_id(self):
        # Opened from a project, the copies go on that project whichever bid is picked.
        if self.env.context.get("twp_bid_copy_project"):
            return
        for wizard in self:
            wizard.opportunity_id = wizard.bid_id.opportunity_id

    @api.depends("bid_id", "opportunity_id")
    def _compute_already_bid_ids(self):
        for wizard in self:
            if wizard.opportunity_id == wizard.bid_id.opportunity_id:
                bids = wizard.bid_id | wizard.bid_id._twp_competing_bids()
            else:
                bids = self.env["sale.order"].search([
                    ("opportunity_id", "=", wizard.opportunity_id.id),
                    ("twp_is_bid", "=", True),
                    ("twp_bid_status", "=", "open"),
                ]) if wizard.opportunity_id else self.env["sale.order"]
            wizard.already_bid_ids = bids.partner_id

    def action_apply(self):
        self.ensure_one()
        bid = self.bid_id
        if not bid.twp_is_bid:
            raise UserError(_("%s is no longer a bid, so it can't be copied to other bidders.", bid.name))
        copies = self.env["sale.order"]
        for partner in self.partner_ids:
            copies |= bid._twp_copy_for(partner, self.opportunity_id)
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
