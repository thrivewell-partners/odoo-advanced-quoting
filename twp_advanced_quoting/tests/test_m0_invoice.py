import re

from odoo.tests import TransactionCase, tagged

from .common import QuoteCase


@tagged("post_install", "-at_install")
class TestInvoiceBundle(QuoteCase, TransactionCase):
    """M0 proof 5: an invoiced bundle prints its package price, and its members without prices."""

    def render(self, invoice):
        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "account.report_invoice", invoice.ids
        )
        return html.decode()

    def cell(self, html, css_class):
        match = re.search(rf'class="[^"]*\b{css_class}\b[^"]*"[^>]*>\s*([^<]*?)\s*<', html)
        return match and match.group(1)

    def deliver(self, order, heater, bracket, labor):
        for product, qty in ((self.heater, heater), (self.bracket, bracket), (self.labor, labor)):
            self.line(order, product).qty_delivered = qty

    def test_full_invoice(self):
        order = self.make_order(bundle_only=True)
        order.action_confirm()
        invoice = order._create_invoices()
        section = invoice.invoice_line_ids.filtered(lambda l: l.display_type == "line_section")
        self.assertTrue(section.twp_is_bundle)
        self.assertTrue(section.collapse_prices)

        html = self.render(invoice)
        self.assertIn("Heater package", html)
        self.assertEqual(self.cell(html, "twp_bundle_qty"), "5.00")
        self.assertEqual(self.cell(html, "twp_package_price"), "1,260.00")
        self.assertIn("6,300.00", html)
        self.assertIn("TWP Heater", html)
        self.assertIn("TWP Bracket", html)
        self.assertNotIn("TWP Labor", html)
        # Member prices never print.
        self.assertNotIn("1,000.00", html)

    def test_partial_invoice(self):
        for product in (self.heater, self.bracket, self.labor):
            product.invoice_policy = "delivery"
        order = self.make_order(bundle_only=True)
        order.action_confirm()
        self.deliver(order, heater=2, bracket=6, labor=2)
        html = self.render(order._create_invoices())
        self.assertEqual(self.cell(html, "twp_bundle_qty"), "2.00")
        self.assertEqual(self.cell(html, "twp_package_price"), "1,260.00")
        self.assertIn("2,520.00", html)
        self.assertNotIn("TWP Labor", html)

    def test_uneven_partial_invoice(self):
        """Members delivered in different shares make no whole package count.

        The bundle row then prints like Odoo's own Hide Prices section: its name and total,
        members with their quantities and no prices.
        """
        for product in (self.heater, self.bracket, self.labor):
            product.invoice_policy = "delivery"
        order = self.make_order(bundle_only=True)
        order.action_confirm()
        self.deliver(order, heater=2, bracket=3, labor=2)
        html = self.render(order._create_invoices())
        self.assertIsNone(self.cell(html, "twp_bundle_qty"))
        self.assertIsNone(self.cell(html, "twp_package_price"))
        self.assertIn("Heater package", html)
        # 2 x 1,000 + 3 x 20 + 2 x 200
        self.assertIn("2,460.00", html)
        self.assertIn("TWP Bracket", html)
        self.assertNotIn("TWP Labor", html)
