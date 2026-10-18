from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    twp_bid_title = fields.Char(
        string="Bid Title",
        translate=True,
        default="Bid",
        help="Printed as the title of a bid, in place of the style's title, until the bid is won.",
    )
