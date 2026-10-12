from odoo import fields, models


class TwpDocumentStyle(models.Model):
    _name = "twp.document.style"
    _description = "Quote Document Style"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    title_word = fields.Char(
        string="Title Word",
        translate=True,
        help="Printed in place of Quotation, such as Estimate or Proposal.",
    )
    totals_mode = fields.Selection(
        [("full", "Full"), ("options", "Full, with each option"), ("hidden", "Hidden")],
        string="Totals",
        default="full",
        required=True,
        help="Full prints the total of what is included. With each option adds the total with each "
             "alternative or add-on not yet chosen. A quote of nothing but options prints no total.",
    )
    show_line_numbers = fields.Boolean(
        string="Line Numbers",
        help="Number each product row on the quote and the customer's online page.",
    )
    show_code_column = fields.Boolean(
        string="Code Column",
        help="Print the product's internal reference in its own column, and take it off the description.",
    )
    code_column_label = fields.Char(
        string="Code Column Label",
        translate=True,
        default="Model No.",
    )
