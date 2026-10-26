from odoo import fields, models
from odoo.tools import float_compare


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    twp_is_bundle = fields.Boolean(string="Bundle")
    twp_standalone = fields.Boolean(string="Standalone Lines")
    twp_qty_per_bundle = fields.Float(string="Per Bundle", digits="Product Unit")
    twp_hide_on_documents = fields.Boolean(string="Hide on Documents")
    twp_hide_price = fields.Boolean(string="Hide Price")

    def _twp_invoiced_bundle_qty(self, member_lines):
        """How many packages these member lines make, or False when they disagree.

        A partial invoice can carry two of five packages; it can also carry a different
        share of each member, and then there is no package count to print.
        """
        ratios = [
            line.quantity / line.twp_qty_per_bundle
            for line in member_lines
            if line.display_type == "product" and line.twp_qty_per_bundle
        ]
        if not ratios:
            return False
        digits = self.env["decimal.precision"].precision_get("Product Unit")
        if any(float_compare(ratio, ratios[0], precision_digits=digits) for ratio in ratios):
            return False
        return ratios[0]

    def _get_detailed_lines(self, children_lines, direct_children_lines, subsection_lines):
        result = super()._get_detailed_lines(
            children_lines,
            direct_children_lines.filtered(lambda line: not line.twp_hide_on_documents),
            subsection_lines,
        )
        if self.twp_is_bundle and result and result[0].get("display_type") == self.display_type:
            summary = result[0]
            bundle_qty = self._twp_invoiced_bundle_qty(children_lines)
            summary["twp_is_bundle"] = True
            summary["twp_bundle_qty"] = bundle_qty
            summary["twp_package_price"] = summary["price_subtotal"] / bundle_qty if bundle_qty else False
        return result
