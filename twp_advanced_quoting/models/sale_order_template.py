from odoo import fields, models


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    twp_introduction = fields.Html(
        string="Introduction",
        translate=True,
        help="Printed above the lines of a quote made from this template, in place of the default in Settings.",
    )
