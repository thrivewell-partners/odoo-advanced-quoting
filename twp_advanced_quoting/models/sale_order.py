from odoo import _, api, fields, models
from odoo.exceptions import UserError
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

    # Numbers. With separate order numbers on, `name` is the quote number until the order is
    # confirmed, then the order number; both are kept.
    twp_quote_number = fields.Char(string="Quote Number", copy=False, readonly=True, index="btree_not_null")
    twp_order_number = fields.Char(string="Order Number", copy=False, readonly=True, index="btree_not_null")

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

    twp_section_margins = fields.Html(
        string="Margins by Section",
        compute="_compute_twp_section_margins",
        sanitize=False,
        help="The amount, cost and margin of each section, bundle and option, from the lines' own margins.",
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

    @api.depends(
        "order_line.margin",
        "order_line.price_subtotal",
        "order_line.sequence",
        "order_line.display_type",
        "order_line.name",
        "order_line.twp_is_bundle",
        "order_line.twp_bundle_qty",
    )
    def _compute_twp_section_margins(self):
        for order in self:
            rows = order._twp_section_margin_rows()
            order.twp_section_margins = self.env["ir.qweb"]._render(
                "twp_advanced_quoting.section_margins",
                {"order": order, "rows": rows, "show_bundle_qty": any(row["bundle_qty"] for row in rows)},
            ) if rows else False

    def _twp_section_margin_rows(self):
        """[{name, subsection, bundle_qty, amount, cost, margin, margin_percent}] per section."""
        self.ensure_one()
        self.order_line._twp_refresh_parents()
        rows = []
        for section in self.order_line.filtered(
            lambda line: line.display_type in ("line_section", "line_subsection") and not line.is_downpayment
        ):
            lines = section._get_section_lines().filtered(lambda line: not line._twp_is_special())
            if not lines:
                continue
            amount = sum(lines.mapped("price_subtotal"))
            margin = sum(lines.mapped("margin"))
            rows.append({
                "name": section.name,
                "subsection": section.display_type == "line_subsection",
                "bundle_qty": section.twp_bundle_qty if section.twp_is_bundle else False,
                "amount": amount,
                "cost": amount - margin,
                "margin": margin,
                "margin_percent": margin / amount if amount else False,
            })
        return rows

    @api.onchange("order_line")
    def _twp_onchange_bundles(self):
        # The editor shows a member's quantity follow its bundle before the quote is saved.
        self.order_line._twp_sync_bundles()

    @property
    def _rec_names_search(self):
        return [*super()._rec_names_search, "twp_quote_number", "twp_order_number"]

    # ------------------------------------------------------------
    # Order numbers
    # ------------------------------------------------------------

    def action_confirm(self):
        # Checked here as well as in super, so a refused confirmation spends no order number.
        for order in self:
            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)
        # Numbered before super, so deliveries, purchases and the confirmation email carry it.
        self.filtered(lambda order: order.company_id.twp_number_orders)._twp_take_order_number()
        return super().action_confirm()

    def _twp_take_order_number(self):
        for order in self:
            quote_number = order.twp_quote_number or order.name
            order_number = order.twp_order_number or self.env["ir.sequence"].with_company(
                order.company_id
            ).next_by_code("twp.sale.order.confirmed", sequence_date=fields.Date.context_today(order))
            if not order_number:
                continue
            order.write({
                "twp_quote_number": quote_number,
                "twp_order_number": order_number,
                "name": order_number,
            })
            order.message_post(body=_("Quote %(quote)s confirmed as order %(order)s.", quote=quote_number, order=order_number))

    def action_draft(self):
        # Back to a quote: it reads as the quote it was. Confirming again reuses its order number.
        orders = self.filtered(lambda order: order.state in ("cancel", "sent"))
        result = super().action_draft()
        for order in orders.filtered(lambda o: o.twp_quote_number and o.name == o.twp_order_number):
            order.name = order.twp_quote_number
        return result

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
        """{line id: number} for the numbered rows among the lines to print.

        A bundle takes one number on its own row and its members print without one; every
        other product row is numbered.
        """
        numbered = lines.filtered(
            lambda line: line.twp_is_bundle if line.display_type
            else line.product_type != "combo" and not line._twp_bundle()
        )
        return {line.id: number for number, line in enumerate(numbered, start=1)}

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
