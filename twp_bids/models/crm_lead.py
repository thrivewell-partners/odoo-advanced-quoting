from odoo import _, api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    twp_bid_count = fields.Integer(string="Number of Bids", compute="_compute_twp_bid_count")

    @api.depends("order_ids.twp_bid_number")
    def _compute_twp_bid_count(self):
        for lead in self:
            lead.twp_bid_count = len(lead.order_ids.filtered("twp_bid_number"))

    # Bids are not quotations: the Quotations button counts and lists neither.
    def _get_lead_quotation_domain(self):
        return [*super()._get_lead_quotation_domain(), ("twp_is_bid", "=", False)]

    def _get_action_view_sale_quotation_domain(self):
        return [*super()._get_action_view_sale_quotation_domain(), ("twp_is_bid", "=", False)]

    def action_twp_new_bid(self):
        """A new bid on this opportunity. The bidder is chosen on the bid, not taken from the lead."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("twp_bids.action_bids")
        context = self._prepare_opportunity_quotation_context()
        context.pop("default_partner_id", None)
        context.update(default_twp_is_bid=True, default_twp_job_name=self.name)
        action.update({
            "context": context,
            "views": [(self.env.ref("sale.view_order_form").id, "form")],
            "view_mode": "form",
            "name": _("New Bid"),
        })
        return action

    def action_twp_view_bids(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("twp_bids.action_bids")
        context = self._prepare_opportunity_quotation_context()
        context.pop("default_partner_id", None)
        context.update(default_twp_is_bid=True, default_twp_job_name=self.name)
        action["context"] = context
        action["domain"] = [("opportunity_id", "=", self.id), ("twp_bid_number", "!=", False)]
        return action
