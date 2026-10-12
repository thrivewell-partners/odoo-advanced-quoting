from odoo import api, fields, models
from odoo.tools import float_compare

OPTION_MODES = [
    ("included", "Included"),
    ("alternative", "Alternative"),
    ("addon", "Add-on"),
]

# Writing any of these can change a bundle member's ordered quantity.
BUNDLE_FIELDS = {
    "twp_is_bundle",
    "twp_bundle_qty",
    "twp_qty_per_bundle",
    "sequence",
    "display_type",
    "order_id",
}


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Sections and subsections
    twp_is_bundle = fields.Boolean(
        string="Bundle",
        help="Prints as one priced package row, its members listed below without prices.",
    )
    twp_bundle_qty = fields.Float(
        string="Bundle Quantity",
        digits="Product Unit",
        default=1.0,
        help="How many packages. A section's own quantity must stay 0, so it is kept here.",
    )
    twp_option_mode = fields.Selection(
        OPTION_MODES,
        string="Option Mode",
        default="included",
        required=True,
        help="Alternatives and add-ons print in full and stay out of the order total until chosen.",
    )
    twp_option_group = fields.Char(
        string="Option Group",
        help="Alternatives in the same group are choices between each other, such as Option 1 and Option 2.",
    )
    twp_option_chosen = fields.Boolean(
        string="Chosen",
        help="The customer took this alternative or add-on, so it counts in the order total.",
    )

    # Product lines
    twp_qty_per_bundle = fields.Float(
        string="Per Bundle",
        digits="Product Unit",
        help="Quantity in one package. The ordered quantity is this times the bundle quantity.",
    )
    twp_hide_on_documents = fields.Boolean(
        string="Hide on Documents",
        help="Counted in the total, never printed on the quote, the portal or the invoice.",
    )

    # ------------------------------------------------------------
    # Section membership
    # ------------------------------------------------------------

    def _twp_enclosing_sections(self):
        """The line's parent and, through a subsection, its grandparent."""
        self.ensure_one()
        return self.parent_id | self.parent_id.parent_id

    def _twp_bundle(self):
        self.ensure_one()
        if self.display_type:
            return self.browse()
        return self._twp_enclosing_sections().filtered("twp_is_bundle")[:1]

    def _twp_option_section(self):
        self.ensure_one()
        return self._twp_enclosing_sections().filtered(
            lambda section: section.twp_option_mode != "included"
        )[:1]

    def _twp_is_excluded(self):
        """Whether this line is kept out of the order total."""
        self.ensure_one()
        if self.display_type:
            return False
        section = self._twp_option_section()
        return bool(section) and not section.twp_option_chosen

    # ------------------------------------------------------------
    # Bundle quantities, held on the server
    # ------------------------------------------------------------

    def _twp_sync_bundles(self, rederive=None):
        """Set each bundle member's ordered quantity from its per-bundle quantity.

        A member with no per-bundle quantity, or one in `rederive` (its ordered
        quantity was written directly), keeps the quantity it has and takes its
        per-bundle quantity from it.
        """
        rederive = rederive or self.browse()
        digits = self.env["decimal.precision"].precision_get("Product Unit")
        sync = self.with_context(twp_bundle_sync=True)
        for line in sync.filtered(lambda l: not l.display_type):
            bundle = line._twp_bundle()
            if not bundle or not bundle.twp_bundle_qty:
                continue
            if line in rederive or not line.twp_qty_per_bundle:
                per_bundle = line.product_uom_qty / bundle.twp_bundle_qty
                if float_compare(per_bundle, line.twp_qty_per_bundle, precision_digits=digits):
                    line.twp_qty_per_bundle = per_bundle
                continue
            qty = line.twp_qty_per_bundle * bundle.twp_bundle_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=digits):
                line.product_uom_qty = qty

    @api.model
    def _twp_bundle_vals(self, vals):
        if vals.get("twp_is_bundle"):
            # A bundle reuses Odoo's own Hide Prices for its members.
            vals = dict(vals, collapse_prices=True, collapse_composition=False)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._twp_bundle_vals(vals) for vals in vals_list]
        lines = super().create(vals_list)
        if not self.env.context.get("twp_bundle_sync"):
            lines.order_id.order_line._twp_sync_bundles()
        return lines

    def write(self, vals):
        vals = self._twp_bundle_vals(vals)
        result = super().write(vals)
        if self.env.context.get("twp_bundle_sync"):
            return result
        rederive = self.browse()
        if "product_uom_qty" in vals and "twp_qty_per_bundle" not in vals:
            rederive = self
        if BUNDLE_FIELDS & set(vals) or rederive:
            self.order_id.order_line._twp_sync_bundles(rederive=rederive)
        return result

    # ------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------

    def _prepare_invoice_line(self, **optional_values):
        values = super()._prepare_invoice_line(**optional_values)
        values.update(
            twp_is_bundle=self.twp_is_bundle,
            twp_qty_per_bundle=self.twp_qty_per_bundle,
            twp_hide_on_documents=self.twp_hide_on_documents,
        )
        return values
