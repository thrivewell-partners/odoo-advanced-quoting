from odoo import fields, models


class SaleOrderTemplateLine(models.Model):
    _inherit = "sale.order.template.line"

    # Sections and subsections
    twp_is_bundle = fields.Boolean(
        string="Bundle",
        help="Prints as one priced package row, its members listed below without prices. "
             "The quantities of its lines are per bundle.",
    )
    twp_bundle_qty = fields.Float(
        string="Bundle Qty",
        digits="Product Unit",
        default=1.0,
        help="How many packages the quote starts with.",
    )

    # Product lines
    twp_hide_on_documents = fields.Boolean(
        string="Hide on Documents",
        help="Counted in the total, never printed on the quote, the portal or the invoice.",
    )
    twp_hide_price = fields.Boolean(
        string="Hide Price",
        help="Printed with its quantity and no price. Its price still counts in the section and the total.",
    )

    def _twp_bundle(self):
        self.ensure_one()
        if self.display_type:
            return self.browse()
        return (self.parent_id | self.parent_id.parent_id).filtered("twp_is_bundle")[:1]

    def _prepare_order_line_values(self):
        values = super()._prepare_order_line_values()
        if self.display_type:
            if self.twp_is_bundle:
                values.update(twp_is_bundle=True, twp_bundle_qty=self.twp_bundle_qty)
            return values
        values.update(twp_hide_on_documents=self.twp_hide_on_documents, twp_hide_price=self.twp_hide_price)
        bundle = self._twp_bundle()
        if bundle:
            # A template's quantities inside a bundle are per bundle.
            values.update(
                twp_qty_per_bundle=self.product_uom_qty,
                product_uom_qty=self.product_uom_qty * bundle.twp_bundle_qty,
            )
        return values
