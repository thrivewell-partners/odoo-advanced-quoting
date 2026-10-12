from odoo import fields, models


class TwpDocumentStyle(models.Model):
    _name = "twp.document.style"
    _description = "Quote Document Style"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    title_word = fields.Char(
        string="Title Word",
        translate=True,
        help="Printed in place of Quotation, such as Estimate or Proposal.",
    )
    totals_mode = fields.Selection(
        [("full", "Full"), ("hidden", "Hidden")],
        string="Totals",
        default="full",
        required=True,
    )
