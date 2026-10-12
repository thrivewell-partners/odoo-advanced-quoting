from lxml import html as lxml_html

from odoo import Command
from odoo.tests import Form, HttpCase, TransactionCase, tagged

from .test_m1_documents import DocumentCase


class BundleCase(DocumentCase):
    """MJOQ6592's heater package: 5 heaters at 1,000.00, 3 brackets at 20.00 per heater, and a
    200.00 labor line per heater hidden on documents. 6,300.00 untaxed, 1,260.00 a package.
    Costs 600.00 a heater and 10.00 a bracket: 3,150.00, so a 50% margin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.heater.standard_price = 600
        cls.bracket.standard_price = 10

    def setUp(self):
        super().setUp()
        self.env.company.twp_bundle_member_qty = "total"

    def cells(self, page, text, tag="td"):
        tree = lxml_html.fromstring(page)
        for tr in tree.iter("tr"):
            if text in tr.text_content() and not tr.xpath(".//tr"):
                return tr.findall(tag)
        return None

    def texts(self, cells):
        return [" ".join(cell.text_content().split()) for cell in cells]

    def width(self, cells):
        return sum(int(cell.get("colspan") or 1) for cell in cells)


@tagged("post_install", "-at_install")
class TestBundleQuantitiesM2(BundleCase, TransactionCase):
    """D15 on the server: inside a bundle only the quantity per bundle is typed."""

    def test_new_member_reads_its_quantity_as_per_bundle(self):
        order = self.make_order(bundle_only=True)
        order.write({"order_line": [Command.create({
            "product_id": self.fan.id, "product_uom_qty": 2, "sequence": 14,
        })]})
        fan = self.line(order, self.fan)
        self.assertEqual(fan.twp_qty_per_bundle, 2.0)
        self.assertEqual(fan.product_uom_qty, 10.0)

    def test_line_moved_into_the_bundle(self):
        order = self.make_order(bundle_only=True)
        order.write({"order_line": [
            Command.create({"display_type": "line_section", "name": "Extras", "sequence": 45}),
            Command.create({"product_id": self.fan.id, "product_uom_qty": 4, "sequence": 50}),
        ]})
        fan = self.line(order, self.fan)
        self.assertFalse(fan.twp_in_bundle)
        self.assertEqual(fan.product_uom_qty, 4.0)
        fan.sequence = 14
        self.assertTrue(fan.twp_in_bundle)
        self.assertEqual(fan.product_uom_qty, 20.0)

    def test_membership(self):
        order = self.make_order()
        self.assertTrue(self.line(order, self.bracket).twp_in_bundle)
        self.assertFalse(self.line(order, self.fan).twp_in_bundle)
        self.assertFalse(self.section(order, "Heater package").twp_in_bundle)

    def test_bundle_keeps_member_prices_hidden(self):
        # Odoo's section menu turns Show Prices on by writing collapse_prices alone.
        section = self.section(self.make_order(bundle_only=True), "Heater package")
        section.write({"collapse_prices": False})
        self.assertTrue(section.collapse_prices)
        # Hide Composition is still allowed: the bundle then prints as its row alone.
        section.write({"collapse_composition": True, "collapse_prices": False})
        self.assertTrue(section.collapse_composition)
        self.assertFalse(section.collapse_prices)
        section.write({"collapse_composition": False})
        self.assertTrue(section.collapse_prices)

    def test_zero_bundles(self):
        order = self.make_order(bundle_only=True)
        self.section(order, "Heater package").twp_bundle_qty = 0
        self.assertEqual([self.line(order, p).product_uom_qty for p in (self.heater, self.bracket)], [0.0, 0.0])
        self.assertEqual(self.line(order, self.bracket).twp_qty_per_bundle, 3.0)
        self.section(order, "Heater package").twp_bundle_qty = 2
        self.assertEqual(self.line(order, self.bracket).product_uom_qty, 6.0)


@tagged("post_install", "-at_install")
class TestBundleEditor(BundleCase, TransactionCase):
    """The quote form, through its onchanges, as the editor drives it before a save."""

    def test_bundle_quantity_moves_members_before_saving(self):
        order = self.make_order(bundle_only=True)
        with Form(order) as form:
            with form.order_line.edit(0) as section:
                section.twp_bundle_qty = 6
            with form.order_line.edit(2) as bracket:
                self.assertEqual(bracket.product_uom_qty, 18.0)
        self.assertEqual(self.line(order, self.bracket).product_uom_qty, 18.0)

    def test_per_bundle_quantity_moves_the_member_before_saving(self):
        order = self.make_order(bundle_only=True)
        with Form(order) as form:
            with form.order_line.edit(2) as bracket:
                bracket.twp_qty_per_bundle = 4
                self.assertEqual(bracket.product_uom_qty, 20.0)
        self.assertEqual(self.line(order, self.bracket).product_uom_qty, 20.0)

    def test_member_quantity_is_read_only(self):
        order = self.make_order(bundle_only=True)
        with Form(order) as form:
            with form.order_line.edit(1) as heater:
                with self.assertRaises(AssertionError):
                    heater.product_uom_qty = 10

    def test_new_line_in_the_bundle(self):
        order = self.make_order(bundle_only=True)
        with Form(order) as form:
            with form.order_line.new() as line:
                line.product_id = self.fan
                line.sequence = 14
        fan = self.line(order, self.fan)
        self.assertEqual(fan.twp_qty_per_bundle, 1.0)
        self.assertEqual(fan.product_uom_qty, 5.0)

    def test_margins(self):
        order = self.make_order(bundle_only=True)
        rows = order._twp_section_margin_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["name"], row["bundle_qty"], row["amount"], row["margin"]), ("Heater package", 5.0, 6300.0, 3150.0))
        self.assertAlmostEqual(row["margin_percent"], 0.5)
        self.assertIn("50.0%", order.twp_section_margins)
        self.assertIn("Heater package", order.twp_section_margins)

    def test_no_sections_no_margins(self):
        self.assertFalse(self.make_quote().twp_section_margins)

    def test_adjustment_defaults(self):
        product = self.env.ref("twp_advanced_quoting.product_bundle_adjustment")
        self.assertEqual(product.type, "service")
        defaults = self.env["sale.order.line"].with_context(twp_bundle_adjustment=True).default_get(
            ["product_id", "twp_hide_on_documents"]
        )
        self.assertEqual(defaults["product_id"], product.id)
        self.assertTrue(defaults["twp_hide_on_documents"])
        other = self._product("TWP Markup", 0)
        other.type = "service"
        self.env.company.twp_bundle_adjustment_product_id = other
        defaults = self.env["sale.order.line"].with_context(twp_bundle_adjustment=True).default_get(["product_id"])
        self.assertEqual(defaults["product_id"], other.id)

    def test_settings(self):
        settings = self.env["res.config.settings"].create({"twp_bundle_member_qty": "per_bundle"})
        settings.execute()
        self.assertEqual(self.env.company.twp_bundle_member_qty, "per_bundle")


@tagged("post_install", "-at_install")
class TestBundleDocument(BundleCase, TransactionCase):
    """The bundle's row on the quote PDF."""

    def test_bundle_row(self):
        page = self.render_quote(self.make_order(bundle_only=True))
        row = self.texts(self.cells(page, "Heater package"))
        # Description, quantity, unit price, taxes, amount.
        self.assertEqual(row[0], "Heater package")
        self.assertEqual(row[1], "5.00")
        self.assertEqual(row[2], "1,260.00")
        self.assertIn("6,300.00", row[-1])
        self.assertEqual(len(row), len(self.headers(page)))
        bracket = " ".join(self.texts(self.cells(page, "TWP Bracket")))
        self.assertIn("15.00", bracket)
        self.assertNotIn("20.00", bracket)
        self.assertNotIn("300.00", bracket)
        self.assertNotIn("TWP Labor", page)

    def test_members_per_bundle(self):
        self.env.company.twp_bundle_member_qty = "per_bundle"
        page = self.render_quote(self.make_order(bundle_only=True))
        bracket = " ".join(self.texts(self.cells(page, "TWP Bracket")))
        self.assertIn("3.00", bracket)
        self.assertIn("per package", bracket)
        self.assertNotIn("15.00", bracket)

    def test_bundle_row_with_line_numbers_and_codes(self):
        order = self.make_order(bundle_only=True)
        order.twp_document_style_id = self.style
        page = self.render_quote(order)
        row = self.cells(page, "Heater package")
        self.assertEqual(len(row), len(self.headers(page)))
        self.assertEqual(self.texts(row)[3], "5.00")

    def test_bundle_hiding_its_composition(self):
        order = self.make_order(bundle_only=True)
        self.section(order, "Heater package").write({"collapse_composition": True, "collapse_prices": False})
        page = self.render_quote(order)
        self.assertNotIn("TWP Bracket", page)
        row = self.texts(self.cells(page, "Heater package"))
        self.assertEqual(row[1], "5.00")
        self.assertIn("1,260.00", row[2])
        self.assertIn("6,300.00", row[-1])

    def test_bundle_subsection_under_hidden_prices(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({"display_type": "line_section", "name": "Heating", "collapse_prices": True, "sequence": 1}),
                Command.create({
                    "display_type": "line_subsection", "name": "Heater package",
                    "twp_is_bundle": True, "twp_bundle_qty": 2, "sequence": 2,
                }),
                Command.create({"product_id": self.heater.id, "twp_qty_per_bundle": 1, "sequence": 3}),
            ],
        })
        self.assertEqual(self.line(order, self.heater).product_uom_qty, 2.0)
        page = self.render_quote(order)
        row = self.texts(self.cells(page, "Heater package"))
        self.assertEqual(row[1], "2.00")
        self.assertNotIn("1,000.00", " ".join(row))
        self.assertNotIn("2,000.00", " ".join(row))

    def test_plain_sections_unchanged(self):
        order = self.make_order()
        page = self.render_quote(order)
        option = self.cells(page, "Option 1")
        self.assertEqual(self.width(option), len(self.headers(page)))
        self.assertIn("200.00", " ".join(self.texts(option)))


@tagged("post_install", "-at_install")
class TestBundleTemplate(BundleCase, TransactionCase):
    """A quotation template carries a bundle, its quantities per bundle, and the hide flags."""

    def test_template(self):
        template = self.env["sale.order.template"].create({
            "name": "TWP Heater package template",
            "sale_order_template_line_ids": [
                Command.create({"display_type": "line_section", "name": "Heater package",
                                "twp_is_bundle": True, "twp_bundle_qty": 5, "sequence": 1}),
                Command.create({"product_id": self.heater.id, "product_uom_qty": 1, "twp_hide_price": True, "sequence": 2}),
                Command.create({"product_id": self.bracket.id, "product_uom_qty": 3, "sequence": 3}),
                Command.create({"product_id": self.labor.id, "product_uom_qty": 1,
                                "twp_hide_on_documents": True, "sequence": 4}),
                Command.create({"display_type": "line_section", "name": "Extras", "sequence": 5}),
                Command.create({"product_id": self.fan.id, "product_uom_qty": 2, "sequence": 6}),
            ],
        })
        with Form(self.env["sale.order"]) as form:
            form.partner_id = self.partner
            form.sale_order_template_id = template
        order = form.record
        section = self.section(order, "Heater package")
        self.assertTrue(section.twp_is_bundle)
        self.assertEqual(section.twp_bundle_qty, 5.0)
        self.assertTrue(section.collapse_prices)
        self.assertEqual(
            [(self.line(order, p).twp_qty_per_bundle, self.line(order, p).product_uom_qty)
             for p in (self.heater, self.bracket, self.labor)],
            [(1.0, 5.0), (3.0, 15.0), (1.0, 5.0)],
        )
        self.assertTrue(self.line(order, self.heater).twp_hide_price)
        self.assertTrue(self.line(order, self.labor).twp_hide_on_documents)
        self.assertEqual(self.line(order, self.fan).product_uom_qty, 2.0)
        self.assertEqual(order.amount_untaxed, 6300.0 + 1000.0)


@tagged("post_install", "-at_install")
class TestBundlePortal(BundleCase, HttpCase):
    """The bundle's row on the customer's online quote."""

    def portal(self, order):
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_portal(self):
        self.env.company.twp_bundle_member_qty = "per_bundle"
        page = self.portal(self.make_order(bundle_only=True))
        row = self.cells(page, "Heater package")
        self.assertTrue(row)
        text = " ".join(self.texts(row))
        self.assertIn("5.00", text)
        self.assertIn("1,260.00", text)
        self.assertIn("6,300.00", text)
        bracket = " ".join(self.texts(self.cells(page, "TWP Bracket")))
        self.assertIn("3.00", bracket)
        self.assertIn("per package", bracket)
        self.assertNotIn("20.00", bracket)
        self.assertNotIn("TWP Labor", page)
