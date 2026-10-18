from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Bid numbers, written to their sequence as Advanced Quoting writes quote numbers
    twp_bid_prefix = fields.Char(string="Bid Number Prefix")
    twp_bid_padding = fields.Integer(string="Bid Number Digits")
    twp_bid_next_number = fields.Integer(string="Next Bid Number")
    twp_bid_title = fields.Char(related="company_id.twp_bid_title", readonly=False)

    @api.model
    def _twp_bid_sequence(self):
        return self._twp_sequence("twp.sale.order.bid")

    @api.model
    def get_values(self):
        res = super().get_values()
        sequence = self._twp_bid_sequence()
        res.update({
            "twp_bid_prefix": sequence.prefix,
            "twp_bid_padding": sequence.padding,
            "twp_bid_next_number": sequence.number_next_actual,
        })
        return res

    def set_values(self):
        super().set_values()
        self._twp_write_sequence(
            self._twp_bid_sequence(), self.twp_bid_prefix, self.twp_bid_padding, self.twp_bid_next_number
        )
