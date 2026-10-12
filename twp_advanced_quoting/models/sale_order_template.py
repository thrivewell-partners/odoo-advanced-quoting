from odoo import fields, models


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    twp_document_style_id = fields.Many2one(
        "twp.document.style",
        string="Document Style",
        help="For a quote made from this template, when the customer has none of the tags the styles list.",
    )
    twp_introduction = fields.Html(
        string="Introduction",
        translate=True,
        help="Printed above the lines of a quote made from this template, in place of the default in Settings.",
    )
