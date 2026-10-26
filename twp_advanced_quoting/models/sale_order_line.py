from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_repr, float_round
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

# Settled when the order is confirmed (D3); changed again only once it is a quote.
OPTION_FIELDS = {"twp_option_mode", "twp_option_group", "twp_option_chosen"}

# What a standalone divider can't be: it groups nothing, so it neither prices nor hides as one.
STANDALONE_FIELDS = (
    "display_type",
    "twp_standalone",
    "twp_is_bundle",
    "twp_option_mode",
    "collapse_prices",
    "collapse_composition",
    "is_optional",
)


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
    twp_option_label = fields.Char(
        string="Option",
        compute="_compute_twp_option_label",
        help="Alternatives and add-ons stay out of the total until they are chosen.",
    )
    twp_not_chosen = fields.Boolean(
        string="Not Chosen",
        copy=False,
        readonly=True,
        help="Left out when the order was confirmed: kept at quantity 0 as a record, never printed.",
    )
    twp_standalone = fields.Boolean(
        string="Standalone Lines",
        help="Ends the group above it. The lines below print on their own, each with its price, "
             "and this row never prints.",
    )
    twp_quoted_qty = fields.Float(
        string="Quoted Quantity",
        digits="Product Unit",
        copy=False,
        readonly=True,
        help="The quantity quoted, before the order was confirmed without this option.",
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
        lines = self.order_id.order_line
        positions = self._twp_sections_by_line(lines).get(self.id, ())
        return self.browse([lines._ids[position] for position in positions])

    @api.model
    def _twp_sections_by_line(self, lines):
        """{line id: positions in `lines` of its subsection and section}, from one pass.

        Every line asks this, the totals once per line, so a large quote would otherwise read
        its lines once per line. The pass is kept for the transaction against the lines, their
        sequence and their kinds, so any change to those reads them again. It holds positions,
        not records: the editor's unsaved lines are new records each time, equal by id.
        """
        key = (
            tuple(lines._ids),
            tuple(lines.mapped("sequence")),
            tuple(lines.mapped("display_type")),
        )
        memo = self.env.cr.cache.setdefault("twp_sections_by_line", {})
        if key not in memo:
            if len(memo) > 1000:
                memo.clear()
            position_of = {line_id: position for position, line_id in enumerate(lines._ids)}
            by_line = {}
            section = subsection = None
            for line in lines.sorted("sequence"):
                position = position_of[line.id]
                if line.display_type == "line_section":
                    section, subsection = position, None
                    by_line[line.id] = ()
                elif line.display_type == "line_subsection":
                    subsection = position
                    by_line[line.id] = (section,) if section is not None else ()
                else:
                    by_line[line.id] = tuple(p for p in (subsection, section) if p is not None)
            memo[key] = by_line
        return memo[key]

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
        """Whether this line is kept out of the order total.

        A line counts only when every alternative or add-on around it is chosen.
        """
        self.ensure_one()
        if self.display_type or self._twp_is_special():
            return False
        return any(
            section.twp_option_mode != "included" and not section.twp_option_chosen
            for section in self._twp_enclosing_sections()
        )

    # ------------------------------------------------------------
    # Alternatives and add-ons
    # ------------------------------------------------------------

    @api.depends("display_type", "twp_option_mode", "twp_option_chosen", "twp_not_chosen")
    def _compute_twp_option_label(self):
        labels = dict(self._fields["twp_option_mode"]._description_selection(self.env))
        for line in self:
            if not line.display_type or line.twp_option_mode == "included":
                line.twp_option_label = False
            elif line.twp_not_chosen:
                line.twp_option_label = _("Not chosen")
            elif line.twp_option_chosen:
                line.twp_option_label = _("Chosen")
            else:
                line.twp_option_label = labels[line.twp_option_mode]

    def _twp_is_option(self):
        self.ensure_one()
        return self.display_type in ("line_section", "line_subsection") and self.twp_option_mode != "included"

    def _twp_alternatives(self):
        """The alternatives this one is a choice between, itself included.

        Alternatives with the same Option Group are choices between each other; those with no
        group form one set per order.
        """
        self.ensure_one()
        return self.order_id.order_line.filtered(
            lambda line: line._twp_is_option()
            and line.twp_option_mode == "alternative"
            and (line.twp_option_group or "") == (self.twp_option_group or "")
        )

    def _twp_section_members(self):
        """Every line under this section or subsection, in order, its subsections included."""
        self.ensure_one()
        ends = ("line_section",) if self.display_type == "line_section" else ("line_section", "line_subsection")
        members = self.browse()
        inside = False
        for line in self.order_id.order_line.sorted("sequence"):
            if line == self:
                inside = True
            elif inside:
                if line.display_type in ends:
                    break
                if not line._twp_is_special():
                    members |= line
        return members

    def _twp_option_note(self):
        """What a quote prints under an alternative or add-on: whether it is in the total."""
        self.ensure_one()
        if not self._twp_is_option() or self.order_id.state not in ("draft", "sent"):
            return ""
        if self.twp_option_chosen:
            return _("Chosen, included in the total")
        return _("Not included in the total")

    def _twp_keep_one_alternative_chosen(self):
        """A chosen alternative unchooses the others in its set."""
        for line in self.filtered(lambda l: l._twp_is_option() and l.twp_option_mode == "alternative" and l.twp_option_chosen):
            others = line._twp_alternatives().filtered(lambda other: other != line and other.twp_option_chosen)
            if others:
                others.with_context(twp_option_sync=True).twp_option_chosen = False

    @api.constrains("is_optional", "twp_is_bundle", "twp_option_mode")
    def _twp_check_not_optional(self):
        """Odoo's optional section is offered online at quantity 0, which neither a bundle nor an
        option can carry: a bundle sets its members' quantities, and an option prints its price.
        """
        for line in self.filtered(lambda l: l.display_type in ("line_section", "line_subsection")):
            sections = line | line._twp_section_members().filtered("display_type")
            optional = any((line | line._twp_enclosing_sections()).mapped("is_optional"))
            if optional and any(section.twp_is_bundle or section._twp_is_option() for section in sections):
                raise ValidationError(_(
                    "%(section)s is an optional section, so it can't be a bundle, an alternative or "
                    "an add-on. Unset Optional first.",
                    section=line.name,
                ))

    @api.constrains(*STANDALONE_FIELDS)
    def _twp_check_standalone(self):
        for line in self.filtered("twp_standalone"):
            if line.display_type != "line_section":
                raise ValidationError(_("Only a section can start standalone lines."))
            if (
                line.twp_is_bundle
                or line._twp_is_option()
                or line.collapse_prices
                or line.collapse_composition
                or line.is_optional
            ):
                raise ValidationError(_(
                    "%(section)s starts standalone lines, so it can't be a bundle, an alternative, "
                    "an add-on or optional, and can't hide its prices or lines.",
                    section=line.name,
                ))

    def _twp_check_options_editable(self, vals):
        if OPTION_FIELDS & set(vals) and any(
            line.display_type and line.order_id.state not in ("draft", "sent") for line in self
        ):
            raise UserError(_(
                "The options were settled when the order was confirmed. "
                "Set it back to a quotation to change them."
            ))

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
            if not bundle or line.twp_not_chosen:
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
        lines._twp_keep_one_alternative_chosen()
        if not self.env.context.get("twp_bundle_sync"):
            # A price given with the line survives its first bundle quantity. Odoo counts it as
            # not typed by hand, so the quantity change would otherwise reprice it from the product.
            priced = self.browse([line.id for line, vals in zip(lines, vals_list) if "price_unit" in vals])
            with self.env.protecting([self._fields["price_unit"], self._fields["technical_price_unit"]], priced):
                lines.order_id.order_line._twp_sync_bundles()
        return lines

    def write(self, vals):
        vals = self._twp_bundle_vals(vals)
        if vals.get("twp_option_mode") == "included" and "twp_option_group" not in vals:
            # An option unset is a plain section again, and joins no set of alternatives.
            vals = dict(vals, twp_option_group=False)
        if not self.env.context.get("twp_option_sync"):
            self._twp_check_options_editable(vals)
        result = super().write(vals)
        if not self.env.context.get("twp_option_sync") and (
            vals.get("twp_option_chosen") or vals.get("twp_option_mode") == "alternative" or "twp_option_group" in vals
        ):
            self._twp_keep_one_alternative_chosen()
        if not self.env.context.get("twp_bundle_sync") and BUNDLE_FIELDS & set(vals):
            self.order_id.order_line._twp_sync_bundles()
        return result

    def copy_data(self, default=None):
        # A copy of a confirmed order quotes its options again at the quantities they were quoted at.
        vals_list = super().copy_data(default=default)
        for line, vals in zip(self, vals_list):
            if line.twp_not_chosen and not line.display_type and "product_uom_qty" not in (default or {}):
                vals["product_uom_qty"] = line.twp_quoted_qty
        return vals_list

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

    def _twp_per_bundle_label(self):
        """A member's quantity per bundle as QuoteWerks prints it before the description: "(3)".

        One per bundle prints nothing, as in QuoteWerks.
        """
        self.ensure_one()
        digits = self.env["decimal.precision"].precision_get("Product Unit")
        qty = float_round(self.twp_qty_per_bundle, precision_digits=digits)
        if float_compare(qty, 1.0, precision_digits=digits) == 0:
            return ""
        return f"({float_repr(qty, digits).rstrip('0').rstrip('.')})"

    # ------------------------------------------------------------
    # Bundle adjustments
    # ------------------------------------------------------------

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        if values.get("twp_standalone") and "name" in fields and not values.get("name"):
            values["name"] = _("Standalone items")
        if self.env.context.get("twp_bundle_adjustment"):
            product = self.env.company._twp_bundle_adjustment_product()
            if product and "product_id" in fields:
                values["product_id"] = product.id
            if "twp_hide_on_documents" in fields:
                values["twp_hide_on_documents"] = True
        return values

    # ------------------------------------------------------------
    # Product catalog
    # ------------------------------------------------------------

    def get_parent_section_line(self):
        # In the catalog a line belongs to the innermost section or subsection around it.
        if self.env.context.get("twp_catalog_group") and not self.display_type:
            return self._twp_enclosing_sections()[:1]
        return super().get_parent_section_line()

    def _get_product_catalog_lines_data(self, **kwargs):
        # A bundle member is counted per bundle, as it is typed in the editor.
        data = super()._get_product_catalog_lines_data(**kwargs)
        if len(self) == 1 and self._twp_bundle():
            data["quantity"] = self.twp_qty_per_bundle
        return data

    # ------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------

    def _prepare_invoice_line(self, **optional_values):
        values = super()._prepare_invoice_line(**optional_values)
        values.update(
            twp_is_bundle=self.twp_is_bundle,
            twp_standalone=self.twp_standalone,
            twp_qty_per_bundle=self.twp_qty_per_bundle,
            twp_hide_on_documents=self.twp_hide_on_documents,
            twp_hide_price=self.twp_hide_price,
        )
        return values
