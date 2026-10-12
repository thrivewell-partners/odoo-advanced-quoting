from odoo import api, fields, models
from odoo.tools import float_compare
from odoo.tools.misc import unique

OPTION_MODES = [
    ("included", "Included"),
    ("alternative", "Alternative"),
    ("addon", "Add-on"),
]

# Writing any of these can change a bundle member's ordered quantity, or a bundle's prices.
BUNDLE_FIELDS = {
    "twp_is_bundle",
    "twp_bundle_qty",
    "twp_qty_per_bundle",
    "product_uom_qty",
    "sequence",
    "display_type",
    "order_id",
    "collapse_prices",
    "collapse_composition",
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
    twp_in_bundle = fields.Boolean(
        string="In a Bundle",
        compute="_compute_twp_in_bundle",
        help="Inside a bundle only the quantity per bundle is typed; the ordered quantity follows it.",
    )
    twp_hide_on_documents = fields.Boolean(
        string="Hide on Documents",
        help="Counted in the total, never printed on the quote, the portal or the invoice.",
    )
    twp_hide_price = fields.Boolean(
        string="Hide Price",
        help="Printed with its quantity and no price. Its price still counts in the section and the total.",
    )

    # ------------------------------------------------------------
    # Section membership
    # ------------------------------------------------------------

    def _twp_refresh_parents(self):
        """Drop the cached parent_id of every line on these lines' orders.

        Odoo computes parent_id from sequence with no dependencies, so once read it stays
        cached for the transaction, through any resequencing.
        """
        self.order_id.order_line.invalidate_recordset(["parent_id"])

    def _twp_enclosing_sections(self):
        """The line's subsection, then its section, read from the order's sequence.

        Read here rather than from Odoo's parent_id, which a new line's own onchange can't
        compute, and which stays cached through a resequence.
        """
        self.ensure_one()
        section = subsection = self.browse()
        for line in self.order_id.order_line.sorted("sequence"):
            if line == self:
                if self.display_type == "line_section":
                    return self.browse()
                if self.display_type == "line_subsection":
                    return section
                return subsection | section
            if line.display_type == "line_section":
                section, subsection = line, self.browse()
            elif line.display_type == "line_subsection":
                subsection = line
        return self.browse()

    def _twp_is_special(self):
        # A global discount or down payment is appended under whatever section is last.
        return self.is_downpayment or self._is_global_discount()

    def _twp_bundle(self):
        self.ensure_one()
        if self.display_type or self._twp_is_special():
            return self.browse()
        return self._twp_enclosing_sections().filtered("twp_is_bundle")[:1]

    @api.depends(
        "order_id.order_line.sequence",
        "order_id.order_line.display_type",
        "order_id.order_line.twp_is_bundle",
    )
    def _compute_twp_in_bundle(self):
        for line in self:
            line.twp_in_bundle = bool(line._twp_bundle())

    def _twp_option_section(self):
        self.ensure_one()
        return self._twp_enclosing_sections().filtered(
            lambda section: section.twp_option_mode != "included"
        )[:1]

    def _twp_is_excluded(self):
        """Whether this line is kept out of the order total."""
        self.ensure_one()
        if self.display_type or self._twp_is_special():
            return False
        section = self._twp_option_section()
        return bool(section) and not section.twp_option_chosen

    # ------------------------------------------------------------
    # Bundle quantities, held on the server
    # ------------------------------------------------------------

    def _twp_sync_bundles(self):
        """Hold each bundle member's ordered quantity at its quantity per bundle times the bundle's.

        Inside a bundle only the quantity per bundle is typed (D15); an ordered quantity written
        to a member directly is put back. A line that joins a bundle with no quantity per bundle
        yet reads its ordered quantity as one, so a new line typed as 1 is 1 per bundle. A bundle
        prints its members without prices, unless it hides its composition altogether.
        """
        self._twp_refresh_parents()
        digits = self.env["decimal.precision"].precision_get("Product Unit")
        for line in self.with_context(twp_bundle_sync=True):
            if line.display_type:
                if line.twp_is_bundle and not line.collapse_composition and not line.collapse_prices:
                    line.collapse_prices = True
                continue
            bundle = line._twp_bundle()
            if not bundle:
                continue
            if not line.twp_qty_per_bundle:
                line.twp_qty_per_bundle = line.product_uom_qty
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
            # A price given with the line survives its first bundle quantity. Odoo counts it as
            # not typed by hand, so the quantity change would otherwise reprice it from the product.
            priced = self.browse([line.id for line, vals in zip(lines, vals_list) if "price_unit" in vals])
            with self.env.protecting([self._fields["price_unit"], self._fields["technical_price_unit"]], priced):
                lines.order_id.order_line._twp_sync_bundles()
        return lines

    def write(self, vals):
        vals = self._twp_bundle_vals(vals)
        result = super().write(vals)
        if not self.env.context.get("twp_bundle_sync") and BUNDLE_FIELDS & set(vals):
            self.order_id.order_line._twp_sync_bundles()
        return result

    # ------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------

    def _twp_code(self):
        self.ensure_one()
        return self.product_id.default_code or ""

    def _twp_name_without_code(self):
        """The description with the product's internal reference taken off its front.

        Odoo writes new lines as "[CODE] Name". When the code prints in its own column it
        would otherwise print twice.
        """
        self.ensure_one()
        code = self._twp_code()
        name = self.name or ""
        prefix = f"[{code}]"
        if code and name.startswith(prefix):
            return name[len(prefix):].lstrip()
        return name

    def _twp_bundle_row(self, price_field):
        """What a bundle's own row prints: packages, the price of one, and the bundle's amount.

        The amount is the section's total, so members hidden from documents are priced in. A
        bundle inside a section that hides its prices prints its quantity only.
        """
        self.ensure_one()
        amount = self._get_section_totals(price_field)
        qty = self.twp_bundle_qty
        return {
            "qty": qty,
            "package_price": amount / qty if qty else False,
            "amount": amount,
            "show_prices": not (self.display_type == "line_subsection" and self.parent_id.collapse_prices),
        }

    def _twp_section_tax_labels(self, attribute="tax_label"):
        self.ensure_one()
        taxes = self._get_section_lines().tax_ids
        return ", ".join(unique(label for label in taxes.mapped(attribute) if label))

    def _twp_print_per_bundle(self):
        """Whether this member prints its quantity per bundle rather than in total."""
        self.ensure_one()
        return self.order_id.company_id.twp_bundle_member_qty == "per_bundle" and bool(self._twp_bundle())

    # ------------------------------------------------------------
    # Bundle adjustments
    # ------------------------------------------------------------

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        if self.env.context.get("twp_bundle_adjustment"):
            product = self.env.company._twp_bundle_adjustment_product()
            if product and "product_id" in fields:
                values["product_id"] = product.id
            if "twp_hide_on_documents" in fields:
                values["twp_hide_on_documents"] = True
        return values

    # ------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------

    def _prepare_invoice_line(self, **optional_values):
        values = super()._prepare_invoice_line(**optional_values)
        values.update(
            twp_is_bundle=self.twp_is_bundle,
            twp_qty_per_bundle=self.twp_qty_per_bundle,
            twp_hide_on_documents=self.twp_hide_on_documents,
            twp_hide_price=self.twp_hide_price,
        )
        return values
