from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOrderAndInvoiceNumbers(TransactionCase):
    """Confirmed orders numbered REDO, invoices REDI, quotes staying REDQ."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "TWP Numbers Customer"})
        cls.product = cls.env["product.product"].create({
            "name": "TWP Numbered Heater", "type": "consu", "list_price": 100, "invoice_policy": "order",
        })
        # A sales journal with nothing in it yet, as at a go-live.
        cls.journal = cls.env["account.journal"].create({
            "name": "TWP Radiant Sales", "code": "TWPRS", "type": "sale",
        })

    def setUp(self):
        super().setUp()
        # Per test: the counters are database sequences, which a test's rollback does not undo.
        self.env["res.config.settings"].create({
            "twp_quote_prefix": "REDQ", "twp_quote_padding": 4, "twp_quote_next_number": 1,
            "twp_number_orders": True,
            "twp_order_prefix": "REDO", "twp_order_padding": 4, "twp_order_next_number": 1,
            "twp_invoice_prefix": "REDI", "twp_invoice_padding": 4,
        }).execute()

    def quote(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": 1})],
        })

    def test_confirm_takes_an_order_number(self):
        order = self.quote()
        self.assertEqual(order.name, "REDQ0001")
        order.action_confirm()
        self.assertEqual(order.name, "REDO0001")
        self.assertEqual(order.twp_quote_number, "REDQ0001")
        self.assertEqual(order.twp_order_number, "REDO0001")
        self.assertTrue(any("REDQ0001" in (message.body or "") for message in order.message_ids))
        # The next quote carries on in the quote series, the next order in the order series.
        second = self.quote()
        self.assertEqual(second.name, "REDQ0002")
        second.action_confirm()
        self.assertEqual(second.name, "REDO0002")

    def test_found_by_its_quote_number(self):
        order = self.quote()
        order.action_confirm()
        found = self.env["sale.order"].search([("display_name", "ilike", order.twp_quote_number)])
        self.assertIn(order, found)
        self.assertIn(order, self.env["sale.order"].search([("twp_quote_number", "=", "REDQ0001")]))

    def test_refused_confirmation_spends_no_number(self):
        order = self.quote()
        order.action_confirm()
        with self.assertRaises(Exception):
            order.action_confirm()
        self.assertEqual(order.name, "REDO0001")
        self.assertEqual(self.quote().name, "REDQ0002")
        next_order = self.quote()
        next_order.action_confirm()
        self.assertEqual(next_order.name, "REDO0002")

    def test_back_to_quote_and_confirmed_again(self):
        order = self.quote()
        order.action_confirm()
        order._action_cancel()
        order.action_draft()
        self.assertEqual(order.name, "REDQ0001")
        order.action_confirm()
        self.assertEqual(order.name, "REDO0001")

    def test_copy_is_a_new_quote(self):
        order = self.quote()
        order.action_confirm()
        copy = order.copy()
        self.assertEqual(copy.name, "REDQ0002")
        self.assertFalse(copy.twp_quote_number)
        self.assertFalse(copy.twp_order_number)

    def test_turned_off(self):
        self.env.company.twp_number_orders = False
        order = self.quote()
        order.action_confirm()
        self.assertEqual(order.name, "REDQ0001")
        self.assertFalse(order.twp_order_number)

    def test_order_pdf_shows_the_quote_number(self):
        order = self.quote()
        order.action_confirm()
        html, _type = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", order.ids)
        html = html.decode()
        self.assertIn("REDO0001", html)
        self.assertIn("Quote Number", html)
        self.assertIn("REDQ0001", html)

    def test_invoice_numbers(self):
        order = self.quote()
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.journal_id = self.journal
        invoice.action_post()
        self.assertEqual(invoice.name, "REDI0001")
        self.assertEqual(invoice.invoice_origin, "REDO0001")
        second = self.quote()
        second.action_confirm()
        invoice = second._create_invoices()
        invoice.journal_id = self.journal
        invoice.action_post()
        self.assertEqual(invoice.name, "REDI0002")

    def test_credit_note_number(self):
        order = self.quote()
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.journal_id = self.journal
        invoice.action_post()
        refund = invoice._reverse_moves()
        refund.action_post()
        self.assertEqual(refund.name, "RREDI0001")
