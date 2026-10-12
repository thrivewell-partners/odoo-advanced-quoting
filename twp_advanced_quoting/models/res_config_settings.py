from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Quote numbers, written to the sale.order sequence
    twp_quote_prefix = fields.Char(string="Quote Number Prefix")
    twp_quote_padding = fields.Integer(string="Quote Number Digits")
    twp_quote_next_number = fields.Integer(string="Next Quote Number")

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
    def _twp_quote_sequence(self):
        """The sequence that numbers this company's quotes, as `next_by_code` picks it."""
        sequence = self.env["ir.sequence"].sudo().search(
            [("code", "=", "sale.order"), ("company_id", "in", [self.env.company.id, False])],
            order="company_id",
            limit=1,
        )
        # The next number is read from the database sequence, which moves outside the ORM.
        sequence.invalidate_recordset(["number_next_actual"])
        return sequence

    @api.model
    def get_values(self):
        res = super().get_values()
        sequence = self._twp_quote_sequence()
        res.update(
            twp_quote_prefix=sequence.prefix,
            twp_quote_padding=sequence.padding,
            twp_quote_next_number=sequence.number_next_actual,
        )
        return res

    def set_values(self):
        super().set_values()
        sequence = self._twp_quote_sequence()
        if not sequence:
            return
        if self.twp_quote_next_number < 1:
            raise ValidationError(_("The next quote number must be 1 or more."))
        if self.twp_quote_padding < 0:
            raise ValidationError(_("The number of digits in a quote number can't be negative."))
        # Written only when changed, so saving Settings never touches the sequence by accident.
        vals = {}
        if (self.twp_quote_prefix or "") != (sequence.prefix or ""):
            vals["prefix"] = self.twp_quote_prefix or ""
        if self.twp_quote_padding != sequence.padding:
            vals["padding"] = self.twp_quote_padding
        if self.twp_quote_next_number != sequence.number_next_actual:
            vals["number_next_actual"] = self.twp_quote_next_number
        if vals:
            sequence.write(vals)
