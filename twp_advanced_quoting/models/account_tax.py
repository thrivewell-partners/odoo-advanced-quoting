from odoo import models


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _twp_without_excluded(self, base_lines):
        """Drop base lines built from sale order lines that are kept out of the total.

        The discount wizard and the down payment wizard each build base lines from every
        order line rather than from `_get_priced_lines`, and both pass them through here.
        """
        return [
            base_line for base_line in base_lines
            if not (
                isinstance(base_line.get("record"), models.BaseModel)
                and base_line["record"]._name == "sale.order.line"
                and base_line["record"]._twp_is_excluded()
            )
        ]

    def _prepare_global_discount_lines(self, base_lines, *args, **kwargs):
        return super()._prepare_global_discount_lines(
            self._twp_without_excluded(base_lines), *args, **kwargs
        )

    def _prepare_down_payment_lines(self, base_lines, *args, **kwargs):
        return super()._prepare_down_payment_lines(
            self._twp_without_excluded(base_lines), *args, **kwargs
        )
