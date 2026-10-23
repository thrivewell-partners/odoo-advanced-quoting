from odoo import Command
from odoo.tests import HttpCase, new_test_user, tagged

from .common import QuoteCase


@tagged("post_install", "-at_install")
class TestCatalogGroups(QuoteCase, HttpCase):
    """The product catalog adds to any section or subsection, and counts a bundle member per bundle.

    Odoo's catalog lists top-level sections only, matches a line to its top section, and sets a
    line's ordered quantity, which a bundle puts back.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(cls.env, login="twp_m6_manager", groups="sales_team.group_sale_manager")

    def setUp(self):
        super().setUp()
        self.authenticate(self.manager.login, self.manager.login)

    def catalog(self, route, order, **params):
        response = self.opener.post(
            url=f"{self.base_url()}/product/catalog/{route}",
            json={"params": {"res_model": "sale.order", "order_id": order.id, "child_field": "order_line", **params}},
        )
        return response.json()["result"]

    def set_qty(self, order, product, quantity, group):
        return self.catalog("update_order_line_info", order, product_id=product.id, quantity=quantity, section_id=group.id)

    def catalog_qty(self, order, product, group):
        info = self.catalog("order_lines_info", order, product_ids=product.ids, section_id=group.id)
        return info[str(product.id)]

    def heater_options(self):
        """Heaters, with Option 1 and Option 2 as alternative subsections, each one heater."""
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({"display_type": "line_section", "name": "Heaters", "sequence": 10}),
                Command.create({
                    "display_type": "line_subsection", "name": "Option 1",
                    "twp_option_mode": "alternative", "sequence": 20,
                }),
                Command.create({"product_id": self.heater.id, "product_uom_qty": 2, "sequence": 21}),
                Command.create({
                    "display_type": "line_subsection", "name": "Option 2",
                    "twp_option_mode": "alternative", "sequence": 30,
                }),
                Command.create({"product_id": self.heater.id, "product_uom_qty": 3, "sequence": 31}),
            ],
        })

    def in_group(self, order, product, group):
        return order.order_line.filtered(
            lambda l: l.product_id == product and l._twp_enclosing_sections()[:1] == group
        )

    def test_subsections_listed_under_their_section(self):
        order = self.heater_options()
        sections = self.catalog("get_sections", order)
        self.assertEqual(
            [(s["name"], s["depth"], s["line_count"]) for s in sections],
            [("Heaters", 0, 0), ("Option 1", 1, 1), ("Option 2", 1, 1)],
        )

    def test_same_product_in_two_subsections(self):
        order = self.heater_options()
        option_one, option_two = self.section(order, "Option 1"), self.section(order, "Option 2")
        info = self.catalog_qty(order, self.heater, option_two)
        self.assertEqual(info["quantity"], 3)
        self.assertFalse(info["readOnly"])

        self.set_qty(order, self.heater, 4, option_two)
        self.assertEqual(self.in_group(order, self.heater, option_one).product_uom_qty, 2)
        self.assertEqual(self.in_group(order, self.heater, option_two).product_uom_qty, 4)

        self.set_qty(order, self.heater, 0, option_two)
        self.assertFalse(self.in_group(order, self.heater, option_two))
        self.assertEqual(self.in_group(order, self.heater, option_one).product_uom_qty, 2)

    def test_add_to_a_subsection_or_its_section(self):
        order = self.heater_options()
        heaters, option_one = self.section(order, "Heaters"), self.section(order, "Option 1")
        self.set_qty(order, self.bracket, 1, option_one)
        self.set_qty(order, self.labor, 1, heaters)
        self.assertEqual(
            order.order_line.sorted("sequence").mapped(lambda l: l.product_id.name or l.name),
            ["Heaters", "TWP Labor", "Option 1", "TWP Heater", "TWP Bracket", "Option 2", "TWP Heater"],
        )
        self.assertEqual(self.in_group(order, self.bracket, option_one).product_uom_qty, 1)
        self.assertEqual(self.in_group(order, self.labor, heaters).product_uom_qty, 1)

    def test_bundle_member_counted_per_bundle(self):
        order = self.make_order(bundle_only=True)
        package = self.section(order, "Heater package")
        bracket = self.line(order, self.bracket)
        self.assertEqual(self.catalog_qty(order, self.bracket, package)["quantity"], 3)

        self.set_qty(order, self.bracket, 4, package)
        self.assertEqual((bracket.twp_qty_per_bundle, bracket.product_uom_qty), (4, 20))
        self.assertEqual(self.catalog_qty(order, self.bracket, package)["quantity"], 4)

        self.set_qty(order, self.fan, 1, package)
        fan = self.line(order, self.fan)
        self.assertEqual((fan.twp_qty_per_bundle, fan.product_uom_qty), (1, 5))
        self.assertEqual(self.catalog_qty(order, self.fan, package)["quantity"], 1)
        self.set_qty(order, self.fan, 2, package)
        self.assertEqual((fan.twp_qty_per_bundle, fan.product_uom_qty), (2, 10))

        self.set_qty(order, self.fan, 0, package)
        self.assertFalse(fan.exists())

    def test_bundle_member_to_zero_on_an_order(self):
        order = self.make_order(bundle_only=True)
        order.action_confirm()
        package = self.section(order, "Heater package")
        bracket = self.line(order, self.bracket)
        self.set_qty(order, self.bracket, 0, package)
        self.assertEqual((bracket.twp_qty_per_bundle, bracket.product_uom_qty), (0, 0))

    def test_adding_above_a_bundle_keeps_its_quantities(self):
        order = self.make_order(bundle_only=True)
        order.write({"order_line": [
            Command.create({"display_type": "line_section", "name": "Freight", "sequence": 1}),
            Command.create({"product_id": self.fan.id, "product_uom_qty": 2, "sequence": 2}),
        ]})
        quantities = {line: line.product_uom_qty for line in order.order_line}
        self.set_qty(order, self.option_one, 1, self.section(order, "Freight"))
        self.assertEqual({line: line.product_uom_qty for line in quantities}, quantities)
        self.assertEqual(self.line(order, self.option_one)._twp_enclosing_sections(), self.section(order, "Freight"))

    def test_drag_a_section_with_its_subsections(self):
        order = self.heater_options()
        order.write({"order_line": [
            Command.create({"display_type": "line_section", "name": "Fans", "sequence": 40}),
            Command.create({"product_id": self.fan.id, "product_uom_qty": 1, "sequence": 41}),
        ]})
        heaters, fans = self.section(order, "Heaters"), self.section(order, "Fans")
        sequences = self.catalog("resequence_sections", order, sections=[
            {"id": heaters.id, "sequence": heaters.sequence},
            {"id": fans.id, "sequence": fans.sequence},
        ])
        self.assertEqual(
            order.order_line.sorted("sequence").mapped(lambda l: l.product_id.name or l.name),
            ["Fans", "TWP Fan", "Heaters", "Option 1", "TWP Heater", "Option 2", "TWP Heater"],
        )
        self.assertEqual(sequences[str(heaters.id)], heaters.sequence)
        self.assertEqual(self.in_group(order, self.heater, self.section(order, "Option 2")).product_uom_qty, 3)

    def test_a_subsection_is_not_dragged(self):
        order = self.heater_options()
        option_one, option_two = self.section(order, "Option 1"), self.section(order, "Option 2")
        before = order.order_line.sorted("sequence").ids
        sequences = self.catalog("resequence_sections", order, sections=[
            {"id": option_two.id, "sequence": option_two.sequence},
            {"id": option_one.id, "sequence": option_one.sequence},
        ])
        self.assertEqual(sequences, {})
        self.assertEqual(order.order_line.sorted("sequence").ids, before)

    def test_filter_reads_the_selected_group(self):
        order = self.heater_options()
        order.write({"order_line": [
            Command.create({"product_id": self.bracket.id, "product_uom_qty": 1, "sequence": 22}),
        ]})
        products = self.env["product.product"].with_context(
            order_id=order.id,
            product_catalog_order_model="sale.order",
            child_field="order_line",
            section_id=self.section(order, "Option 2").id,
        ).search([("is_in_selected_section_of_order", "=", True)])
        self.assertEqual(products, self.heater)
