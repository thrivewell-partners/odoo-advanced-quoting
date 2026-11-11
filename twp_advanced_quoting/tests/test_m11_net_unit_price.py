from odoo import Command
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestNetUnitPrice(TransactionCase):
    """The quote screen shows each line's unit price with its discount taken off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "TWP M11 Customer"})
        cls.clamp = cls.env["product.product"].create({"name": "TWP M11 Clamp", "list_price": 36.0})

    def test_net_unit_price(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({"display_type": "line_section", "name": "TWP M11 Parts"}),
                Command.create({"product_id": self.clamp.id, "product_uom_qty": 4, "discount": 20}),
            ],
        })
        section, line = order.order_line.sorted("sequence")
        self.assertEqual(section.twp_net_price_unit, 0.0)
        self.assertAlmostEqual(line.price_unit, 36.0)
        self.assertAlmostEqual(line.twp_net_price_unit, 28.8)
        line.discount = 0
        self.assertAlmostEqual(line.twp_net_price_unit, 36.0)

    def test_column_follows_the_discounts_setting(self):
        """With Discounts off Unit Price is already net, so the column stays away."""
        def form_arch(groups):
            user = new_test_user(self.env, login=f"twp_m11_{len(groups)}", groups=groups)
            views = self.env["sale.order"].with_user(user).get_views([(False, "form")])
            return views["views"]["form"]["arch"]

        salesman = "sales_team.group_sale_salesman"
        self.assertIn("twp_net_price_unit", form_arch(f"{salesman},sale.group_discount_per_so_line"))
        if not self.env.ref("base.group_user").implied_ids & self.env.ref("sale.group_discount_per_so_line"):
            self.assertNotIn("twp_net_price_unit", form_arch(salesman))
