from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_m1_documents import DocumentCase


@tagged("post_install", "-at_install")
class TestLineDescription(DocumentCase, TransactionCase):
    """A sales description that only repeats the product's name is left off a new line.

    Radiant's imported catalog fills it with the name, or the reference and the name, so every
    quote printed the description twice.
    """

    def line_name(self, description):
        self.heater.description_sale = description
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [Command.create({"product_id": self.heater.id})],
        })
        return order.order_line.name

    def test_same_as_name(self):
        self.assertEqual(self.line_name("TWP Heater"), "[HL3-30] TWP Heater")
        self.assertEqual(self.line_name("  twp   heater "), "[HL3-30] TWP Heater")

    def test_reference_then_name(self):
        self.assertEqual(self.line_name("HL3-30 TWP Heater"), "[HL3-30] TWP Heater")
        self.assertEqual(self.line_name("HL3-30 - TWP Heater"), "[HL3-30] TWP Heater")

    def test_description_that_says_more(self):
        self.assertEqual(
            self.line_name("TWP Heater, 30,000 BTU, natural gas"),
            "[HL3-30] TWP Heater\nTWP Heater, 30,000 BTU, natural gas",
        )
        self.assertEqual(self.line_name("HL3-30"), "[HL3-30] TWP Heater\nHL3-30")


@tagged("post_install", "-at_install")
class TestPortalLineDescription(DocumentCase, HttpCase):
    """The online quote prints the description once, with eCommerce installed or not."""

    def test_portal(self):
        self.heater.description_sale = "HL3-30 TWP Heater"
        order = self.make_quote(twp_document_style_id=self.style.id)
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        heater = self.row(response.text, "TWP Heater")
        self.assertEqual(heater[:3], ["1", "TWP Heater", "HL3-30"])
        self.style.show_code_column = False
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(self.row(response.text, "TWP Heater")[1], "[HL3-30] TWP Heater")
