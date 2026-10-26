from lxml import html as lxml_html

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_m1_documents import DocumentCase


class StandaloneCase(DocumentCase):
    """The heater package, then a standalone divider with two accessories below it.

    The bundle is 6,300.00 untaxed, as in QuoteCase. The accessories are two thermostats at
    180.00 and a flue kit at 300.00, each on its own: 6,300 + 360 + 300 = 6,960.00.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.thermostat = cls._product("TWP Thermostat", 180)
        cls.flue = cls._product("TWP Flue Kit", 300)

    def make_standalone_order(self, **values):
        order = self.make_order(bundle_only=True)
        order.write({
            "order_line": [
                Command.create({
                    "display_type": "line_section",
                    "name": "Standalone items",
                    "twp_standalone": True,
                    "sequence": 50,
                }),
                Command.create({"product_id": self.thermostat.id, "product_uom_qty": 2, "sequence": 51}),
                Command.create({"product_id": self.flue.id, "product_uom_qty": 1, "sequence": 52}),
            ],
            **values,
        })
        return order

    def divider(self, order):
        return order.order_line.filtered("twp_standalone")

    def cell_classes(self, page, text):
        """The class of the first cell in the table row that mentions `text`."""
        tree = lxml_html.fromstring(page)
        for tr in tree.iter("tr"):
            if text in tr.text_content() and not tr.xpath(".//tr"):
                return tr.findall("td")[0].get("class") or ""
        return None


@tagged("post_install", "-at_install")
class TestStandaloneLines(StandaloneCase, TransactionCase):

    def test_lines_leave_the_bundle(self):
        order = self.make_standalone_order()
        thermostat = self.line(order, self.thermostat)
        self.assertFalse(thermostat.twp_in_bundle)
        # Typed as 2, not 2 per bundle of 5.
        self.assertEqual(thermostat.product_uom_qty, 2)
        self.assertEqual(self.line(order, self.bracket).product_uom_qty, 15)

    def test_saving_a_divider_leaves_the_lines_below_alone(self):
        """The editor saves a new divider after the bundle with the lines below it renumbered.

        Written one at a time, Option 1 moved first and left its line under the bundle for a
        moment, which took the bundle's quantity: 2 became 10.
        """
        order = self.make_order()
        option = self.section(order, "Option 1")
        line = self.line(order, self.option_one)
        order.write({"order_line": [
            Command.update(option.id, {"sequence": 22}),
            Command.update(line.id, {"sequence": 23}),
            Command.create({
                "display_type": "line_section",
                "name": "Standalone items",
                "twp_standalone": True,
                "sequence": 20,
            }),
        ]})
        self.assertEqual(line.product_uom_qty, 2)
        self.assertFalse(line.twp_in_bundle)
        self.assertEqual(self.line(order, self.bracket).product_uom_qty, 15)

    def test_a_priced_line_added_to_a_bundle_keeps_its_price(self):
        order = self.make_order(bundle_only=True)
        order.write({"order_line": [Command.create({
            "product_id": self.thermostat.id, "product_uom_qty": 1, "price_unit": 150, "sequence": 14,
        })]})
        thermostat = self.line(order, self.thermostat)
        self.assertEqual(thermostat.product_uom_qty, 5)
        self.assertEqual(thermostat.price_unit, 150)

    def test_total(self):
        self.assertEqual(self.make_standalone_order().amount_untaxed, 6960.0)

    def test_divider_groups_nothing(self):
        divider = self.divider(self.make_standalone_order())
        for values in (
            {"twp_is_bundle": True},
            {"twp_option_mode": "alternative"},
            {"twp_option_mode": "addon"},
            {"collapse_prices": True},
            {"collapse_composition": True},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError), self.env.cr.savepoint():
                divider.write(values)

    def test_only_a_section_is_a_divider(self):
        order = self.make_standalone_order()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.write({"order_line": [Command.create({
                "display_type": "line_subsection",
                "name": "Standalone subsection",
                "twp_standalone": True,
                "sequence": 60,
            })]})

    def test_quote_prints_no_divider(self):
        page = self.render_quote(self.make_standalone_order())
        self.assertNotIn("Standalone items", page)
        thermostat = self.row(page, "TWP Thermostat")
        self.assertIn("180.00", " ".join(thermostat))
        self.assertIn("360.00", " ".join(thermostat))
        # Flush left, as a line above every section prints; the bundle's members stay indented.
        self.assertNotIn("px-", self.cell_classes(page, "TWP Thermostat"))
        self.assertIn("px-", self.cell_classes(page, "TWP Bracket"))

    def test_line_numbers_run_on(self):
        order = self.make_standalone_order(twp_document_style_id=self.style.id)
        page = self.render_quote(order)
        self.assertEqual(self.row(page, "Heater package")[0], "1")
        self.assertEqual(self.row(page, "TWP Thermostat")[0], "2")
        self.assertEqual(self.row(page, "TWP Flue Kit")[0], "3")

    def test_invoice_prints_no_divider(self):
        order = self.make_standalone_order()
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertTrue(invoice.invoice_line_ids.filtered("twp_standalone"))
        page = self.render_invoice(invoice)
        self.assertNotIn("Standalone items", page)
        self.assertIn("360.00", " ".join(self.row(page, "TWP Thermostat")))
        self.assertNotIn("px-", self.cell_classes(page, "TWP Thermostat"))


@tagged("post_install", "-at_install")
class TestUnsetOption(StandaloneCase, TransactionCase):

    def test_unset_alternative(self):
        order = self.make_order()
        option = self.section(order, "Option 1")
        option.twp_option_mode = "included"
        self.assertFalse(option.twp_option_group)
        self.assertFalse(option.twp_option_chosen)
        # Option 1 is now part of the order: 6,300 + 2 x 100.
        self.assertEqual(order.amount_untaxed, 6500.0)
        # Option 2 is the only alternative left in its set.
        self.assertEqual(self.section(order, "Option 2")._twp_alternatives(), self.section(order, "Option 2"))


@tagged("post_install", "-at_install")
class TestStandalonePortal(StandaloneCase, HttpCase):

    def test_portal(self):
        order = self.make_standalone_order()
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Standalone items", response.text)
        self.assertIn("360.00", " ".join(self.row(response.text, "TWP Thermostat")))
        self.assertNotIn("px-", self.cell_classes(response.text, "TWP Thermostat"))
