from odoo import fields, models


class TwpDocumentStyle(models.Model):
    _name = "twp.document.style"
    _description = "Quote Document Style"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="Leave empty to use the style in every company.",
    )
    tag_ids = fields.Many2many(
        "res.partner.category",
        string="Customer Tags",
        help="A quote takes the first style, in order, that has a tag of the customer's company. "
             "A customer with none of these tags gets the default style from Settings.",
    )
    structure = fields.Selection(
        [("grouped", "Grouped"), ("itemized", "Itemized")],
        string="Structure",
        default="grouped",
        required=True,
        help="Itemized prints every product line with its own quantity and price: no bundles, "
             "alternatives, add-ons, hidden lines or hidden prices. Grouped allows them all.",
    )
    title_word = fields.Char(
        string="Title Word",
        translate=True,
        help="Printed in place of Quotation, such as Estimate or Proposal.",
    )
    order_title_word = fields.Char(
        string="Order Title Word",
        translate=True,
        default="Order",
        help="Printed on a confirmed order, and on the signed copy saved when the customer accepts.",
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
    discount_column = fields.Selection(
        [("show", "When a line has a discount"), ("net", "Never, net prices only")],
        string="Discount Column",
        default="show",
        required=True,
        help="Net prices only prints each unit price with its discount taken off, and no discount column.",
    )
    show_taxes = fields.Boolean(
        string="Taxes Column",
        default=True,
        help="Print each line's taxes in their own column.",
    )

    # Which header fields print, among those turned on in Settings
    print_job_name = fields.Boolean(string="Job Name", default=True)
    print_ship_via = fields.Boolean(string="Ship Via", default=True)
    print_fob = fields.Boolean(string="FOB", default=True)
    print_freight = fields.Boolean(string="Freight", default=True)
    print_lead_time = fields.Boolean(string="Estimated Lead Time", default=True)
    print_introduction = fields.Boolean(string="Introduction", default=True)

    def _twp_prints(self, suffix):
        """Whether quotes in this style print a header field. No style prints them all."""
        return not self or self[f"print_{suffix}"]

    def _twp_match(self, partner, company):
        """The first style, in order, with a tag of the partner's company."""
        tags = partner.commercial_partner_id.category_id
        if not tags:
            return self.browse()
        return self.search(
            [("tag_ids", "in", tags.ids), ("company_id", "in", [company.id, False])],
            limit=1,
        )

