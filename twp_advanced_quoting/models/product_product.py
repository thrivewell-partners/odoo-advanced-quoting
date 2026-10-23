from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _search_is_in_selected_section_of_order(self, operator, value):
        # The catalog's Filter switch reads the group the way the quote's catalog does.
        if self.env.context.get("product_catalog_order_model") == "sale.order":
            self = self.with_context(twp_catalog_group=True)
        return super(ProductProduct, self)._search_is_in_selected_section_of_order(operator, value)
