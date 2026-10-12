import re

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import QuoteCase


class DocumentCase(QuoteCase):
    """A plain itemized quote with the M1 fields filled in.

    Lines: a heater at 1,000.00 with its price hidden, two brackets at 20.00, and a labor
    line at 200.00 hidden from documents. Untaxed: 1,000 + 40 + 200 = 1,240.00.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.heater.default_code = "HL3-30"
        cls.bracket.default_code = "SMB"
        cls.style = cls.env["twp.document.style"].create({
            "name": "TWP M1 Numbered",
            "show_line_numbers": True,
            "show_code_column": True,
            "code_column_label": "Model No.",
        })

    def make_quote(self, **values):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "twp_job_name": "Main Street School",
            "twp_ship_via": "Best Way",
            "twp_fob": "Origin",
            "twp_freight": "Prepaid and Add",
            "twp_lead_time": "2-3 weeks",
            "twp_introduction": "<p>Here is the quote you requested.</p>",
            "order_line": [
                Command.create({"product_id": self.heater.id, "product_uom_qty": 1, "twp_hide_price": True}),
                Command.create({"product_id": self.bracket.id, "product_uom_qty": 2}),
                Command.create({"product_id": self.labor.id, "product_uom_qty": 1, "twp_hide_on_documents": True}),
            ],
            **values,
        })

    def render_quote(self, order):
        html, _type = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", order.ids)
        return html.decode()

    def render_invoice(self, invoice):
        html, _type = self.env["ir.actions.report"]._render_qweb_html("account.report_invoice", invoice.ids)
        return html.decode()

    def row(self, page, text):
        """The text of each cell in the table row that mentions `text`."""
        tree = lxml_html.fromstring(page)
        for tr in tree.iter("tr"):
            if text in tr.text_content() and not tr.xpath(".//tr"):
                return [" ".join(td.text_content().split()) for td in tr.findall("td")]
        return None

    def headers(self, page):
        tree = lxml_html.fromstring(page)
        table = tree.xpath("//table[contains(@class, 'o_main_table') or @id='sales_order_table']")[0]
        return [" ".join(th.text_content().split()) for th in table.iter("th")]


@tagged("post_install", "-at_install")
class TestQuoteDocument(DocumentCase, TransactionCase):
    """M1 on the quote PDF."""

    def test_amounts(self):
        order = self.make_quote()
        self.assertEqual(order.amount_untaxed, 1240.0)

    def test_header_fields_and_introduction(self):
        page = self.render_quote(self.make_quote())
        for text in ("Job Name", "Main Street School", "Ship Via", "Best Way", "FOB", "Origin",
                     "Freight", "Prepaid and Add", "Estimated Lead Time", "2-3 weeks"):
            self.assertIn(text, page)
        intro = page.index("Here is the quote you requested.")
        self.assertLess(intro, page.index("TWP Bracket"))

    def test_field_turned_off_and_renamed(self):
        self.env.company.twp_freight_enabled = False
        self.env.company.twp_job_name_label = "Project"
        page = self.render_quote(self.make_quote())
        self.assertNotIn("Prepaid and Add", page)
        self.assertIn("Project", page)
        self.assertNotIn("Job Name", page)

    def test_hide_price(self):
        page = self.render_quote(self.make_quote())
        heater = self.row(page, "TWP Heater")
        self.assertTrue(heater)
        self.assertNotIn("1,000.00", " ".join(heater))
        self.assertIn("1.00", " ".join(heater))
        # The next row is priced again.
        self.assertIn("40.00", " ".join(self.row(page, "TWP Bracket")))
        # The hidden price still counts.
        self.assertIn("1,240.00", page)

    def test_hide_on_documents(self):
        page = self.render_quote(self.make_quote())
        self.assertNotIn("TWP Labor", page)

    def test_no_style_no_extra_columns(self):
        page = self.render_quote(self.make_quote())
        self.assertNotIn("Model No.", self.headers(page))
        self.assertIn("[SMB] TWP Bracket", page)

    def test_code_column_and_line_numbers(self):
        page = self.render_quote(self.make_quote(twp_document_style_id=self.style.id))
        headers = self.headers(page)
        self.assertEqual(headers[:3], ["#", "Description", "Model No."])
        bracket = self.row(page, "TWP Bracket")
        self.assertEqual(bracket[:3], ["2", "TWP Bracket", "SMB"])
        self.assertNotIn("[SMB]", page)
        self.assertEqual(self.row(page, "TWP Heater")[:3], ["1", "TWP Heater", "HL3-30"])

    def test_section_spans_the_extra_columns(self):
        order = self.make_quote(twp_document_style_id=self.style.id)
        order.write({"order_line": [Command.create({
            "display_type": "line_section", "name": "TWP Heaters", "sequence": 0,
        })]})
        page = self.render_quote(order)
        tree = lxml_html.fromstring(page)
        section = [
            tr for tr in tree.iter("tr") if "TWP Heaters" in tr.text_content() and not tr.xpath(".//tr")
        ][0]
        # #, description, code, quantity, unit price and taxes; the amount has its own cell.
        self.assertEqual(section.findall("td")[0].get("colspan"), "6")


@tagged("post_install", "-at_install")
class TestQuoteDefaults(DocumentCase, TransactionCase):

    def test_job_name_copies(self):
        copy = self.make_quote().copy()
        self.assertEqual(copy.twp_job_name, "Main Street School")

    def test_default_introduction(self):
        self.env.company.twp_introduction_default = "<p>Thank you for the opportunity.</p>"
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertIn("Thank you for the opportunity.", order.twp_introduction)

    def test_template_introduction(self):
        self.env.company.twp_introduction_default = "<p>Thank you for the opportunity.</p>"
        template = self.env["sale.order.template"].create({
            "name": "TWP M1 template",
            "twp_introduction": "<p>Scope for the boiler room.</p>",
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sale_order_template_id": template.id,
        })
        self.assertIn("Scope for the boiler room.", order.twp_introduction)

    def test_introduction_turned_off(self):
        self.env.company.twp_introduction_default = "<p>Thank you for the opportunity.</p>"
        self.env.company.twp_introduction_enabled = False
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertFalse(order._twp_show_introduction())
        order.twp_introduction = "<p>Typed by hand.</p>"
        self.assertNotIn("Typed by hand.", self.render_quote(order))

    def test_form_labels(self):
        self.env.company.twp_job_name_label = "Project"
        self.env.company.twp_freight_enabled = False
        arch = self.env["sale.order"].get_views([(False, "form")])["views"]["form"]["arch"]
        tree = lxml_html.fromstring(arch)
        job = tree.xpath("//field[@name='twp_job_name']")[0]
        self.assertEqual(job.get("string"), "Project")
        freight = tree.xpath("//field[@name='twp_freight']")[0]
        self.assertEqual(freight.get("invisible"), "1")


@tagged("post_install", "-at_install")
class TestInvoiceDocument(DocumentCase, TransactionCase):
    """M1 on the invoice: Job Name, Hide Price, Hide on Documents."""

    def test_invoice(self):
        order = self.make_quote()
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.twp_job_name, "Main Street School")
        self.assertEqual(invoice.amount_untaxed, 1240.0)
        page = self.render_invoice(invoice)
        self.assertIn("Job Name", page)
        self.assertIn("Main Street School", page)
        self.assertNotIn("TWP Labor", page)
        heater = self.row(page, "TWP Heater")
        self.assertTrue(heater)
        self.assertNotIn("1,000.00", " ".join(heater))
        bracket = self.row(page, "TWP Bracket")
        self.assertIn("40.00", " ".join(bracket))
        # Description, quantity, unit price, taxes, amount: the tax label still prints.
        self.assertTrue(bracket[3])
        self.assertEqual(heater[3], bracket[3])
        # Only the order's header field travels; the shipping fields stay on the order.
        self.assertNotIn("Best Way", page)


@tagged("post_install", "-at_install")
class TestPortalDocument(DocumentCase, HttpCase):
    """M1 on the customer's online quote."""

    def portal(self, order):
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_portal(self):
        page = self.portal(self.make_quote(twp_document_style_id=self.style.id))
        for text in ("Main Street School", "Best Way", "2-3 weeks", "Here is the quote you requested."):
            self.assertIn(text, page)
        self.assertNotIn("TWP Labor", page)
        heater = self.row(page, "TWP Heater")
        self.assertTrue(heater)
        self.assertNotIn("1,000.00", " ".join(heater))
        self.assertEqual(heater[:3], ["1", "TWP Heater", "HL3-30"])
        self.assertIn("40.00", " ".join(self.row(page, "TWP Bracket")))
        self.assertIn("Model No.", self.headers(page))
        # The total still counts the hidden price: 1,240.00 plus 10% tax.
        self.assertTrue(re.search(r"1,364\.00", page))
