from odoo import _, api, fields, models

BID_SEQUENCE = "twp.sale.order.bid"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # A bid stays a bid until it is won; then it is an ordinary quotation that remembers its bid
    # number. The status says how it ended.
    twp_is_bid = fields.Boolean(
        string="Bid",
        index=True,
        help="Sent to one of several bidders. Kept out of Quotations until it is won.",
    )
    twp_bid_number = fields.Char(string="Bid Number", copy=False, readonly=True, index="btree_not_null")
    twp_bid_status = fields.Selection(
        [("open", "Open"), ("won", "Won"), ("lost", "Lost")],
        string="Bid Status",
        copy=False,
        readonly=True,
        tracking=True,
    )
    twp_bid_sent_date = fields.Date(
        string="Bid Sent", copy=False, readonly=True, help="The day the bid was first sent to the bidder."
    )
    twp_bid_source_id = fields.Many2one(
        "sale.order", string="Copied From", copy=False, readonly=True, index="btree_not_null",
        help="The bid this one was copied from by Copy to Customers.",
    )
    twp_bid_copy_count = fields.Integer(compute="_compute_twp_bid_copy_count")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("twp_is_bid", self.env.context.get("default_twp_is_bid")):
                continue
            vals.update(twp_is_bid=True, twp_bid_status="open")
            if vals.get("name", _("New")) == _("New"):
                seq_date = fields.Datetime.context_timestamp(
                    self, fields.Datetime.to_datetime(vals["date_order"])
                ) if "date_order" in vals else None
                vals["name"] = self.env["ir.sequence"].with_company(vals.get("company_id")).next_by_code(
                    BID_SEQUENCE, sequence_date=seq_date
                ) or _("New")
            vals["twp_bid_number"] = vals["name"]
        return super().create(vals_list)

    def write(self, vals):
        unsent = self.filtered(lambda order: order.twp_is_bid and not order.twp_bid_sent_date) if vals.get("state") == "sent" else self.browse()
        result = super().write(vals)
        if unsent:
            unsent.twp_bid_sent_date = fields.Date.context_today(self)
            unsent._twp_bid_sent()
        return result

    def _twp_bid_sent(self):
        """Hook: these bids were just sent for the first time."""

    def _compute_twp_bid_copy_count(self):
        counts = dict(self._read_group(
            [("twp_bid_source_id", "in", self.ids)], ["twp_bid_source_id"], ["__count"]
        )) if self.ids else {}
        for order in self:
            order.twp_bid_copy_count = counts.get(order, 0)

    # ------------------------------------------------------------
    # The document
    # ------------------------------------------------------------

    def _twp_title(self):
        if self.twp_is_bid:
            return (self.company_id or self.env.company).twp_bid_title or _("Bid")
        return super()._twp_title()

    @api.depends("twp_is_bid")
    def _compute_type_name(self):
        return super()._compute_type_name()

    def _find_mail_template(self):
        if self.twp_is_bid and not self.env.context.get("proforma"):
            return self.env.ref("twp_bids.email_template_bid", raise_if_not_found=False) or super()._find_mail_template()
        return super()._find_mail_template()

    def _confirmation_error_message(self):
        if self.twp_is_bid:
            return _("%s is a bid. Mark it won first; it then becomes a quotation that can be confirmed.", self.name)
        return super()._confirmation_error_message()

    def _has_to_be_signed(self):
        return super()._has_to_be_signed() and not self.twp_is_bid

    def _has_to_be_paid(self):
        return super()._has_to_be_paid() and not self.twp_is_bid

    # ------------------------------------------------------------
    # Won and lost
    # ------------------------------------------------------------

    def _twp_competing_bids(self):
        """The other open bids on the same opportunities: the ones a win here beats."""
        opportunities = self.opportunity_id
        if not opportunities:
            return self.browse()
        return self.search([
            ("opportunity_id", "in", opportunities.ids),
            ("twp_is_bid", "=", True),
            ("twp_bid_status", "=", "open"),
            ("id", "not in", self.ids),
        ])

    def action_twp_bid_won(self):
        self._twp_make_quotation()
        self._twp_competing_bids()._twp_mark_lost()
        return True

    def action_twp_bid_lost(self):
        self._twp_mark_lost()
        return True

    def _twp_make_quotation(self):
        """Turn won bids into ordinary quotations, numbered as quotes, to go on through Sales."""
        for order in self.filtered("twp_is_bid"):
            if order.state == "cancel":
                order.action_draft()
            number = self.env["ir.sequence"].with_company(order.company_id).next_by_code(
                "sale.order", sequence_date=fields.Datetime.context_timestamp(order, fields.Datetime.now())
            ) or order.name
            bid_number = order.twp_bid_number or order.name
            order.write({
                "name": number,
                "twp_is_bid": False,
                "twp_bid_number": bid_number,
                "twp_bid_status": "won",
                "state": "draft",
                "date_order": fields.Datetime.now(),
            })
            order.message_post(body=_("Bid %(bid)s won. It is now quotation %(quote)s.", bid=bid_number, quote=number))

    def _twp_mark_lost(self):
        """Lost bids are cancelled, and stay under Bids as a record."""
        bids = self.filtered(lambda order: order.twp_is_bid and order.twp_bid_status != "lost")
        if not bids:
            return
        bids.write({"twp_bid_status": "lost"})
        bids.filtered(lambda order: order.state in ("draft", "sent"))._action_cancel()

    def action_draft(self):
        # A lost bid set back to a quotation is open again.
        reopened = self.filtered(lambda order: order.twp_is_bid and order.twp_bid_status == "lost")
        result = super().action_draft()
        reopened.filtered(lambda order: order.state == "draft").write({"twp_bid_status": "open"})
        return result

    def _twp_copy_for(self, partner):
        """This bid for another bidder: the same lines and prices, the bidder's own addresses,
        payment terms and document style."""
        self.ensure_one()
        order = self.with_company(self.company_id)
        addresses = partner.address_get(["invoice", "delivery"])
        partner = partner.with_company(order.company_id)
        fiscal_position = self.env["account.fiscal.position"].with_company(order.company_id)._get_fiscal_position(
            partner, self.env["res.partner"].browse(addresses["delivery"])
        )
        copy = order.copy({
            "partner_id": partner.id,
            "partner_invoice_id": addresses["invoice"],
            "partner_shipping_id": addresses["delivery"],
            "payment_term_id": (partner.property_payment_term_id or order.payment_term_id).id,
            "fiscal_position_id": fiscal_position.id,
            "twp_bid_source_id": (self.twp_bid_source_id or self).id,
        })
        if copy.fiscal_position_id != self.fiscal_position_id:
            copy._recompute_taxes()
        style = copy._twp_matched_style()
        if style and style != copy.twp_document_style_id:
            copy.twp_document_style_id = style
        return copy

    def action_twp_copy_to_customers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Copy to Customers"),
            "res_model": "twp.bid.copy",
            "view_mode": "form",
            "target": "new",
            "context": {"default_bid_id": self.id},
        }

    def action_twp_view_copies(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("twp_bids.action_bids")
        action["domain"] = [("twp_bid_source_id", "=", self.id)]
        action["context"] = {"create": False}
        return action
