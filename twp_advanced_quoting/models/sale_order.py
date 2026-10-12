from odoo import api, fields, models

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
