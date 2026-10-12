from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Quote and order numbers, written to their sequences
    twp_quote_prefix = fields.Char(string="Quote Number Prefix")
    twp_quote_padding = fields.Integer(string="Quote Number Digits")
    twp_quote_next_number = fields.Integer(string="Next Quote Number")
    twp_number_orders = fields.Boolean(related="company_id.twp_number_orders", readonly=False)
    twp_order_prefix = fields.Char(string="Order Number Prefix")
    twp_order_padding = fields.Integer(string="Order Number Digits")
    twp_order_next_number = fields.Integer(string="Next Order Number")

    # Invoice numbers, read by the first invoice of a sales journal
    twp_invoice_prefix = fields.Char(related="company_id.twp_invoice_prefix", readonly=False)
    twp_invoice_padding = fields.Integer(related="company_id.twp_invoice_padding", readonly=False)

    # Bundles
    twp_bundle_member_qty = fields.Selection(related="company_id.twp_bundle_member_qty", readonly=False)
    twp_bundle_adjustment_product_id = fields.Many2one(
        related="company_id.twp_bundle_adjustment_product_id", readonly=False
    )

    # Header fields
    twp_job_name_enabled = fields.Boolean(related="company_id.twp_job_name_enabled", readonly=False)
    twp_job_name_label = fields.Char(related="company_id.twp_job_name_label", readonly=False)
    twp_ship_via_enabled = fields.Boolean(related="company_id.twp_ship_via_enabled", readonly=False)
    twp_ship_via_label = fields.Char(related="company_id.twp_ship_via_label", readonly=False)
    twp_fob_enabled = fields.Boolean(related="company_id.twp_fob_enabled", readonly=False)
    twp_fob_label = fields.Char(related="company_id.twp_fob_label", readonly=False)
    twp_freight_enabled = fields.Boolean(related="company_id.twp_freight_enabled", readonly=False)
    twp_freight_label = fields.Char(related="company_id.twp_freight_label", readonly=False)
    twp_lead_time_enabled = fields.Boolean(related="company_id.twp_lead_time_enabled", readonly=False)
    twp_lead_time_label = fields.Char(related="company_id.twp_lead_time_label", readonly=False)
    twp_introduction_enabled = fields.Boolean(related="company_id.twp_introduction_enabled", readonly=False)
    twp_introduction_default = fields.Html(related="company_id.twp_introduction_default", readonly=False)

    @api.model
    def _twp_sequence(self, code):
        """The sequence that numbers this company's records with `code`, as `next_by_code` picks it."""
        sequence = self.env["ir.sequence"].sudo().search(
            [("code", "=", code), ("company_id", "in", [self.env.company.id, False])],
            order="company_id",
            limit=1,
        )
        # The next number is read from the database sequence, which moves outside the ORM.
        sequence.invalidate_recordset(["number_next_actual"])
        return sequence

    @api.model
    def _twp_quote_sequence(self):
        return self._twp_sequence("sale.order")

    @api.model
    def _twp_order_sequence(self):
        return self._twp_sequence("twp.sale.order.confirmed")

    @api.model
    def get_values(self):
        res = super().get_values()
        for key, sequence in (("quote", self._twp_quote_sequence()), ("order", self._twp_order_sequence())):
            res.update({
                f"twp_{key}_prefix": sequence.prefix,
                f"twp_{key}_padding": sequence.padding,
                f"twp_{key}_next_number": sequence.number_next_actual,
            })
        return res

    def set_values(self):
        super().set_values()
        for key, sequence in (("quote", self._twp_quote_sequence()), ("order", self._twp_order_sequence())):
            self._twp_write_sequence(
                sequence,
                self[f"twp_{key}_prefix"],
                self[f"twp_{key}_padding"],
                self[f"twp_{key}_next_number"],
            )

    def _twp_write_sequence(self, sequence, prefix, padding, next_number):
        if not sequence:
            return
        if next_number < 1:
            raise ValidationError(_("The next number of %s must be 1 or more.", sequence.name))
        if padding < 0:
            raise ValidationError(_("The number of digits of %s can't be negative.", sequence.name))
        # Written only when changed, so saving Settings never touches a sequence by accident.
        vals = {}
        if (prefix or "") != (sequence.prefix or ""):
            vals["prefix"] = prefix or ""
        if padding != sequence.padding:
            vals["padding"] = padding
        if next_number != sequence.number_next_actual:
            vals["number_next_actual"] = next_number
        if vals:
            sequence.write(vals)
