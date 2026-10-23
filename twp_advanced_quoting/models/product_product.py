from odoo import models

# What may stand between an internal reference and the name in a description: "THGH10 - Cable".
CODE_SEPARATORS = " -:–—"


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _search_is_in_selected_section_of_order(self, operator, value):
        # The catalog's Filter switch reads the group the way the quote's catalog does.
        if self.env.context.get("product_catalog_order_model") == "sale.order":
            self = self.with_context(twp_catalog_group=True)
        return super(ProductProduct, self)._search_is_in_selected_section_of_order(operator, value)

    def get_product_multiline_description_sale(self):
        # A sales description that only says the product's name again is left off the line.
        if self.description_sale and self._twp_description_repeats_name():
            return self.display_name
        return super().get_product_multiline_description_sale()

    def _twp_description_repeats_name(self):
        """Whether the sales description is the product's name, alone or after its reference.

        Imported catalogs often fill it that way, and Odoo writes a new line as the name, then
        the description beneath: the same words twice. Case and spacing are not compared.
        """
        self.ensure_one()

        def words(text):
            return " ".join((text or "").split()).casefold()

        name = words(self.name)
        description = words(self.description_sale)
        if description == name:
            return True
        code = words(self.default_code)
        if code and description.startswith(code):
            return description[len(code):].lstrip(CODE_SEPARATORS) == name
        return False
