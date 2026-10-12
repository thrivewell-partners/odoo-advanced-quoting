from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_m1_documents import DocumentCase


class OptionCase(DocumentCase):
    """MJOQ6922's shape: the 6,300.00 heater package, Option 1 (2 x 100.00) and Option 2
    (1 x 300.00) as alternatives in one set, and the HVLS fan (500.00) as an add-on. 10% tax.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.options_style = cls.env["twp.document.style"].create({
            "name": "TWP M3 With Options",
            "totals_mode": "options",
        })

    def setUp(self):
        super().setUp()
        self.env.company.twp_ask_options_on_confirm = True

    def options_only(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({
                    "display_type": "line_section", "name": "Option 1",
                    "twp_option_mode": "alternative", "sequence": 10,
                }),
                Command.create({"product_id": self.option_one.id, "product_uom_qty": 2, "sequence": 11}),
                Command.create({
                    "display_type": "line_section", "name": "Option 2",
                    "twp_option_mode": "alternative", "sequence": 20,
                }),
                Command.create({"product_id": self.option_two.id, "product_uom_qty": 1, "sequence": 21}),
            ],
        })

    def confirm_from_button(self, order):
        return order.with_context(twp_ask_options=True, validate_analytic=True).action_confirm()


@tagged("post_install", "-at_install")
class TestChoosing(OptionCase, TransactionCase):
    """Alternatives in a set are exclusive; add-ons are not."""

    def test_choosing_an_alternative_unchooses_the_other(self):
        order = self.make_order()
        option_one, option_two = self.section(order, "Option 1"), self.section(order, "Option 2")
        option_one.twp_option_chosen = True
        self.assertEqual(order.amount_untaxed, 6500.0)
        option_two.twp_option_chosen = True
        self.assertFalse(option_one.twp_option_chosen)
        self.assertEqual(order.amount_untaxed, 6600.0)
        self.section(order, "HVLS fan").twp_option_chosen = True
        self.assertTrue(option_two.twp_option_chosen)
        self.assertEqual(order.amount_untaxed, 7100.0)

    def test_sets_are_kept_by_option_group(self):
        order = self.make_order()
        option_one, option_two = self.section(order, "Option 1"), self.section(order, "Option 2")
        option_two.twp_option_group = "Controls"
        option_one.twp_option_chosen = True
        option_two.twp_option_chosen = True
        self.assertTrue(option_one.twp_option_chosen)
        self.assertEqual(order.amount_untaxed, 6800.0)

    def test_labels(self):
        order = self.make_order()
        self.assertEqual(self.section(order, "Option 1").twp_option_label, "Alternative")
        self.assertEqual(self.section(order, "HVLS fan").twp_option_label, "Add-on")
        self.section(order, "HVLS fan").twp_option_chosen = True
        self.assertEqual(self.section(order, "HVLS fan").twp_option_label, "Add-on, chosen")
        self.assertFalse(self.section(order, "Heater package").twp_option_label)
        self.assertFalse(self.line(order, self.fan).twp_option_label)

    def test_line_inside_an_unchosen_addon_stays_out(self):
        # An alternative subsection chosen inside an add-on not chosen is still out.
        order = self.make_order()
        order.write({"order_line": [
            Command.create({
                "display_type": "line_subsection", "name": "Fan controls",
                "twp_option_mode": "alternative", "twp_option_group": "Fan", "twp_option_chosen": True,
                "sequence": 42,
            }),
            Command.create({"product_id": self.option_one.id, "product_uom_qty": 1, "sequence": 43}),
        ]})
        self.assertEqual(order.amount_untaxed, 6300.0)
        self.section(order, "HVLS fan").twp_option_chosen = True
        self.assertEqual(order.amount_untaxed, 6900.0)


@tagged("post_install", "-at_install")
class TestConfirming(OptionCase, TransactionCase):
    """Options not chosen drop to quantity 0 on confirmation and stay as a record (D3)."""

    def test_confirm_without_choosing(self):
        order = self.make_order()
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        for product, quoted in ((self.option_one, 2.0), (self.option_two, 1.0), (self.fan, 1.0)):
            line = self.line(order, product)
            self.assertTrue(line.twp_not_chosen)
            self.assertEqual(line.product_uom_qty, 0.0)
            self.assertEqual(line.twp_quoted_qty, quoted)
        # Prices stay as quoted, for the record.
        self.assertEqual(self.line(order, self.option_two).price_unit, 300.0)
        self.assertTrue(self.section(order, "Option 1").twp_not_chosen)
        self.assertEqual(self.section(order, "Option 1").twp_option_label, "Not chosen")
        self.assertEqual(order.amount_untaxed, 6300.0)
        self.assertEqual(self.line(order, self.heater).product_uom_qty, 5.0)
        self.assertTrue(any("Confirmed without" in body for body in order.message_ids.mapped("body")))

    def test_confirm_with_choices(self):
        order = self.make_order()
        self.section(order, "Option 2").twp_option_chosen = True
        self.section(order, "HVLS fan").twp_option_chosen = True
        order.action_confirm()
        self.assertEqual(self.line(order, self.option_two).product_uom_qty, 1.0)
        self.assertEqual(self.line(order, self.fan).product_uom_qty, 1.0)
        self.assertEqual(self.line(order, self.option_one).product_uom_qty, 0.0)
        self.assertEqual(order.amount_untaxed, 7100.0)

    def test_unchosen_bundle_stays_at_zero(self):
        order = self.make_order()
        package = self.section(order, "Heater package")
        package.write({"twp_option_mode": "alternative", "twp_option_group": "Heater"})
        self.section(order, "Option 1").write({"twp_option_group": "Heater", "twp_option_chosen": True})
        order.action_confirm()
        heater = self.line(order, self.heater)
        self.assertTrue(heater.twp_not_chosen)
        self.assertEqual(heater.product_uom_qty, 0.0)
        self.assertEqual(heater.twp_quoted_qty, 5.0)
        # A write that moves bundles leaves it at 0.
        package.twp_bundle_qty = 6
        self.assertEqual(heater.product_uom_qty, 0.0)
        self.assertEqual(order.amount_untaxed, 200.0)

    def test_back_to_quote_restores_quantities(self):
        order = self.make_order()
        self.section(order, "Option 1").twp_option_chosen = True
        order.action_confirm()
        order._action_cancel()
        order.action_draft()
        self.assertEqual(order.state, "draft")
        self.assertFalse(order.order_line.filtered("twp_not_chosen"))
        self.assertEqual(self.line(order, self.option_two).product_uom_qty, 1.0)
        self.assertEqual(self.line(order, self.fan).product_uom_qty, 1.0)
        self.assertTrue(self.section(order, "Option 1").twp_option_chosen)
        self.assertEqual(order.amount_untaxed, 6500.0)

    def test_options_locked_once_confirmed(self):
        order = self.make_order()
        order.action_confirm()
        with self.assertRaises(UserError):
            self.section(order, "Option 2").twp_option_chosen = True

    def test_copy_quotes_the_options_again(self):
        order = self.make_order()
        order.action_confirm()
        copy = order.copy()
        self.assertFalse(copy.order_line.filtered("twp_not_chosen"))
        self.assertEqual(self.line(copy, self.option_two).product_uom_qty, 1.0)
        self.assertEqual(self.line(copy, self.fan).product_uom_qty, 1.0)
        self.assertEqual(copy.amount_untaxed, 6300.0)

    def test_invoice_has_only_what_was_chosen(self):
        order = self.make_order()
        self.section(order, "Option 2").twp_option_chosen = True
        order.action_confirm()
        invoice = order._create_invoices()
        products = invoice.invoice_line_ids.filtered(lambda l: l.display_type == "product").mapped("product_id")
        self.assertNotIn(self.option_one, products)
        self.assertNotIn(self.fan, products)
        self.assertIn(self.option_two, products)
        self.assertEqual(invoice.amount_untaxed, 6600.0)
        self.assertNotIn("Option 1", invoice.invoice_line_ids.mapped("name"))


@tagged("post_install", "-at_install")
class TestConfirmWizard(OptionCase, TransactionCase):
    """The Confirm button asks what the customer chose."""

    def test_button_opens_the_wizard(self):
        order = self.make_order()
        action = self.confirm_from_button(order)
        self.assertEqual(action["res_model"], "twp.option.choice")
        self.assertEqual(order.state, "draft")
        wizard = self.env["twp.option.choice"].browse(action["res_id"])
        self.assertEqual(wizard.line_ids.mapped("name"), ["Option 1", "Option 2", "HVLS fan"])
        self.assertEqual(wizard.line_ids.mapped("amount"), [200.0, 300.0, 500.0])

    def test_wizard_confirms_the_choice(self):
        order = self.make_order()
        wizard = self.env["twp.option.choice"].browse(self.confirm_from_button(order)["res_id"])
        wizard.line_ids.filtered(lambda l: l.name in ("Option 1", "HVLS fan")).chosen = True
        wizard.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.amount_untaxed, 7000.0)
        self.assertEqual(self.line(order, self.option_two).product_uom_qty, 0.0)

    def test_wizard_refuses_two_alternatives_in_a_set(self):
        order = self.make_order()
        wizard = self.env["twp.option.choice"].browse(self.confirm_from_button(order)["res_id"])
        wizard.line_ids.filtered(lambda l: l.name in ("Option 1", "Option 2")).chosen = True
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(order.state, "draft")

    def test_wizard_switched_off(self):
        self.env.company.twp_ask_options_on_confirm = False
        order = self.make_order()
        self.confirm_from_button(order)
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.amount_untaxed, 6300.0)

    def test_no_options_no_wizard(self):
        order = self.make_order(bundle_only=True)
        self.confirm_from_button(order)
        self.assertEqual(order.state, "sale")


@tagged("post_install", "-at_install")
class TestOptionDocuments(OptionCase, TransactionCase):
    """The totals block, the note on each option, and D2."""

    def test_option_totals(self):
        order = self.make_order()
        rows = {row["name"]: row["amount"] for row in order._twp_option_totals()}
        self.assertEqual(rows, {"Option 1": 7150.0, "Option 2": 7260.0, "HVLS fan": 7480.0})
        # With Option 1 chosen, Option 2 takes its place.
        self.section(order, "Option 1").twp_option_chosen = True
        rows = {row["name"]: row["amount"] for row in order._twp_option_totals()}
        self.assertEqual(rows, {"Option 2": 7260.0, "HVLS fan": 7700.0})

    def test_quote_prints_options_in_full(self):
        order = self.make_order()
        order.twp_document_style_id = self.options_style
        page = self.render_quote(order)
        self.assertIn("200.00", " ".join(self.row(page, "TWP Option One")))
        self.assertIn("Not included in the total", " ".join(self.row(page, "Option 2")))
        self.assertIn("7,260.00", " ".join(self.row(page, "Total with Option 2")))
        # The total is what is included: 6,300.00 plus tax.
        self.assertIn("6,930.00", page)

    def test_full_totals_print_no_option_lines(self):
        page = self.render_quote(self.make_order())
        self.assertNotIn("Total with", page)
        self.assertIn("6,930.00", page)

    def test_confirmed_order_prints_only_what_was_chosen(self):
        order = self.make_order()
        order.twp_document_style_id = self.options_style
        self.section(order, "Option 2").twp_option_chosen = True
        order.action_confirm()
        page = self.render_quote(order)
        self.assertNotIn("TWP Option One", page)
        self.assertNotIn("HVLS fan", page)
        self.assertIn("TWP Option Two", page)
        self.assertNotIn("Not included in the total", page)
        self.assertNotIn("Total with", page)

    def test_options_only_prints_no_total(self):
        order = self.options_only()
        self.assertTrue(order._twp_options_only())
        self.assertEqual(order.amount_total, 0.0)
        page = self.render_quote(order)
        self.assertNotIn("o_total_table", page)
        self.assertIn("200.00", " ".join(self.row(page, "TWP Option One")))
        self.section(order, "Option 1").twp_option_chosen = True
        self.assertFalse(order._twp_options_only())
        self.assertIn("o_total_table", self.render_quote(order))

    def test_customer_cannot_accept_an_open_choice(self):
        order = self.make_order()
        order.require_signature = True
        self.assertTrue(order._twp_needs_choice())
        self.assertFalse(order._has_to_be_signed())
        self.section(order, "Option 1").twp_option_chosen = True
        self.assertFalse(order._twp_needs_choice())
        self.assertTrue(order._has_to_be_signed())


@tagged("post_install", "-at_install")
class TestOptionPortal(OptionCase, HttpCase):
    """The customer's online quote."""

    def portal(self, order):
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_portal_options(self):
        order = self.make_order()
        order.twp_document_style_id = self.options_style
        page = self.portal(order)
        self.assertIn("Not included in the total", page)
        self.assertIn("Total with", page)
        self.assertIn("7,260.00", page)
        self.assertIn("twp_needs_choice", page)

    def test_portal_options_only(self):
        page = self.portal(self.options_only())
        self.assertNotIn("sale_order_totals_table", page)
        self.assertIn("twp_needs_choice", page)
