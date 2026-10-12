from odoo import api, fields, models
from odoo.tools import is_html_empty

from .header_fields import apply_header_field_settings, header_field_cache_key, header_field_settings

# Changing any of these can move a line in or out of the order total.
EXCLUSION_DEPENDS = (
    "order_line.twp_option_mode",
    "order_line.twp_option_chosen",
    "order_line.sequence",
    "order_line.display_type",
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    twp_document_style_id = fields.Many2one(
        "twp.document.style",
        string="Document Style",
        help="How the quote is built and printed.",
    )

    # Header fields. Each company turns them on or off and renames them in Settings.
    twp_job_name = fields.Char(string="Job Name", help="Copied when the quote is duplicated, and carried to the invoice.")
    twp_ship_via = fields.Char(string="Ship Via", help="How the goods ship, such as Best Way.")
    twp_fob = fields.Char(string="FOB", help="Where ownership passes to the customer, such as Origin or Destination.")
    twp_freight = fields.Char(string="Freight", help="Such as Included, Prepaid & Add, or Allowed.")
    twp_lead_time = fields.Char(string="Estimated Lead Time", help="Such as 2-3 weeks.")
    twp_introduction = fields.Html(
        string="Introduction",
        compute="_compute_twp_introduction",
        store=True,
        readonly=False,
        precompute=True,
        help="Printed above the lines.",
    )

    @api.depends("sale_order_template_id")
    def _compute_twp_introduction(self):
        for order in self:
            if not order.company_id.twp_introduction_enabled:
                order.twp_introduction = order.twp_introduction
                continue
            template = order.sale_order_template_id.with_context(lang=order.partner_id.lang)
            if template and not is_html_empty(template.twp_introduction):
                order.twp_introduction = template.twp_introduction
            elif is_html_empty(order.twp_introduction):
                company = order.company_id.with_context(lang=order.partner_id.lang)
                order.twp_introduction = company.twp_introduction_default

    # ------------------------------------------------------------
    # Header fields on the form and the documents
    # ------------------------------------------------------------

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + header_field_cache_key(self.env.company)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            arch = apply_header_field_settings(arch, self.env.company)
            if not self.env.company.twp_introduction_enabled:
                for node in arch.xpath("//page[@name='twp_introduction']"):
                    node.set("invisible", "1")
        return arch, view

    def _twp_header_fields(self):
        """[{name, label, value}] for each header field that is turned on and filled in."""
        self.ensure_one()
        return [
            {"name": name, "label": label, "value": self[name]}
            for name, label, enabled in header_field_settings(self.company_id)
            if enabled and self[name]
        ]

    def _twp_show_introduction(self):
        self.ensure_one()
        return self.company_id.twp_introduction_enabled and not is_html_empty(self.twp_introduction)

    def _twp_line_numbers(self, lines):
        """{line id: number} for the product rows among the lines to print."""
        product_lines = lines.filtered(lambda line: not line.display_type and line.product_type != "combo")
        return {line.id: number for number, line in enumerate(product_lines, start=1)}

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values["twp_job_name"] = self.twp_job_name
        return values

    def _get_priced_lines(self):
        lines = super()._get_priced_lines()
        lines._twp_refresh_parents()
        return lines.filtered(lambda line: not line._twp_is_excluded())

    @api.depends(*EXCLUSION_DEPENDS)
    def _compute_amounts(self):
        return super()._compute_amounts()

    @api.depends(*EXCLUSION_DEPENDS)
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.depends(*EXCLUSION_DEPENDS)
    def _compute_amount_undiscounted(self):
        # Odoo sums every line here itself, and the portal shows the difference from the
        # untaxed amount as the customer's saving, so excluded lines come off.
        super()._compute_amount_undiscounted()
        AccountTax = self.env["account.tax"]
        self.order_line._twp_refresh_parents()
        for order in self:
            for line in order.order_line.filtered(lambda l: l._twp_is_excluded()):
                base_line = line._prepare_base_line_for_taxes_computation(discount=0)
                if not base_line.get("special_type"):
                    AccountTax._add_tax_details_in_base_line(base_line, order.company_id)
                    order.amount_undiscounted -= base_line["tax_details"]["raw_total_excluded_currency"]

    def _get_order_lines_to_report(self):
        return super()._get_order_lines_to_report().filtered(
            lambda line: not line.twp_hide_on_documents
        )
