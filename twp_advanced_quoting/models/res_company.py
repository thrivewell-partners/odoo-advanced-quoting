from odoo import fields, models

ADJUSTMENT_PRODUCT = "twp_advanced_quoting.product_bundle_adjustment"


class ResCompany(models.Model):
    _inherit = "res.company"

    twp_number_orders = fields.Boolean(
        string="Number Confirmed Orders Separately",
        help="A confirmed order takes a number from its own series, and keeps its quote number for reference.",
    )
    twp_invoice_prefix = fields.Char(
        string="Invoice Number Prefix",
        help="The first invoice in a sales journal is numbered with this prefix, such as REDI0001. "
             "A journal that already has invoices carries on with its own pattern.",
    )
    twp_invoice_padding = fields.Integer(string="Invoice Number Digits", default=4)

    twp_bundle_member_qty = fields.Selection(
        [("total", "Total quantity"), ("per_bundle", "Per bundle, as (3)")],
        string="Bundle Member Quantities",
        default="total",
        required=True,
        help="How a bundle's members print their quantities on the quote and the online page: "
             "the total ordered, in the quantity column, or the quantity in one bundle, in brackets "
             "before the description as QuoteWerks prints it. Invoices print what is billed.",
    )
    twp_bundle_adjustment_product_id = fields.Many2one(
        "product.product",
        string="Bundle Adjustment Product",
        domain=[("sale_ok", "=", True), ("type", "=", "service")],
        help="Added by a bundle's Add Adjustment, for markup or labor that is not a catalog item. "
             "It is hidden on documents and priced into the bundle.",
    )

    twp_job_name_enabled = fields.Boolean(string="Job Name", default=True)
    twp_job_name_label = fields.Char(string="Job Name Label", default="Job Name")
    twp_ship_via_enabled = fields.Boolean(string="Ship Via", default=True)
    twp_ship_via_label = fields.Char(string="Ship Via Label", default="Ship Via")
    twp_fob_enabled = fields.Boolean(string="FOB", default=True)
    twp_fob_label = fields.Char(string="FOB Label", default="FOB")
    twp_freight_enabled = fields.Boolean(string="Freight", default=True)
    twp_freight_label = fields.Char(string="Freight Label", default="Freight")
    twp_lead_time_enabled = fields.Boolean(string="Estimated Lead Time", default=True)
    twp_lead_time_label = fields.Char(string="Estimated Lead Time Label", default="Estimated Lead Time")
    twp_introduction_enabled = fields.Boolean(string="Introduction", default=True)
    twp_introduction_default = fields.Html(
        string="Default Introduction",
        translate=True,
        help="Printed above the lines of a new quote, unless its quotation template has its own.",
    )

    def _twp_bundle_adjustment_product(self):
        self.ensure_one()
        return self.twp_bundle_adjustment_product_id or self.env.ref(ADJUSTMENT_PRODUCT, raise_if_not_found=False)
