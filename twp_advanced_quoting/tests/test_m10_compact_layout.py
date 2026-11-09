from lxml import html as lxml_html

from odoo import Command
from odoo.tests import TransactionCase, tagged

from .test_m1_documents import DocumentCase


@tagged("post_install", "-at_install")
class TestCompactLayout(DocumentCase, TransactionCase):
    """M10: the compact layout on quotes and orders, and only on them."""

    def setUp(self):
        super().setUp()
        self.env.company.twp_sale_layout = "compact"

    def tree(self, page):
        return lxml_html.fromstring(page)

    def product_rows(self, page):
        return self.tree(page).xpath("//table[contains(@class, 'o_main_table')]//tr[@name='tr_product']")

    def test_document_layout_by_default(self):
        self.env.company.twp_sale_layout = "company"
        page = self.render_quote(self.make_quote())
        self.assertNotIn("twp_cx_header", page)
        self.assertNotIn("twp_cx_info", page)
        self.assertTrue(self.tree(page).xpath("//div[@id='informations']"))

    def test_header_and_info_row(self):
        order = self.make_quote()
        page = self.render_quote(order)
        tree = self.tree(page)
        header = tree.xpath("//div[contains(@class, 'twp_cx_header')]")[0].text_content()
        self.assertIn("Quotation", header)
        self.assertIn(order.name, header)
        self.assertFalse(tree.xpath("//div[@id='informations']"))
        self.assertFalse(tree.xpath("//div[@id='twp_informations']"))
        customer = tree.xpath("//td[@name='twp_cx_customer']")[0].text_content()
        self.assertIn("Quote for", customer)
        self.assertIn("TWP Test Customer", customer)
        document = " ".join(tree.xpath("//td[@name='twp_cx_document']")[0].text_content().split())
        self.assertIn("Salesperson", document)
        job = " ".join(tree.xpath("//td[@name='twp_cx_job']")[0].text_content().split())
        for text in ("Job Name Main Street School", "Freight Prepaid and Add", "Estimated Lead Time 2-3 weeks"):
            self.assertIn(text, job)

    def pairs(self, tree, box):
        """[(label, value)] in one of the info row's boxes."""
        return [
            tuple(" ".join(cell.text_content().split()) for cell in row.xpath("./td"))
            for row in tree.xpath(f"//td[@name='{box}']//table[contains(@class, 'twp_cx_pairs')]//tr")
        ]

    def test_labels_and_values_in_their_own_cells(self):
        order = self.make_quote()
        tree = self.tree(self.render_quote(order))
        job = self.pairs(tree, "twp_cx_job")
        self.assertIn(("Job Name", "Main Street School"), job)
        self.assertIn(("Freight", "Prepaid and Add"), job)
        self.assertIn(("Estimated Lead Time", "2-3 weeks"), job)
        self.assertEqual(job[0], ("Job Name", "Main Street School"))
        self.assertIn("Salesperson", [label for label, _value in self.pairs(tree, "twp_cx_document")])
        boxes = tree.xpath("//table[@name='twp_cx_info']//td[contains(@class, 'twp_cx_box')]")
        self.assertEqual([box.get("name") for box in boxes], ["twp_cx_customer", "twp_cx_document", "twp_cx_job"])

    def test_job_name_leads(self):
        tree = self.tree(self.render_quote(self.make_quote()))
        feature = tree.xpath("//tr[contains(@class, 'twp_cx_feature')]")
        self.assertEqual(len(feature), 1)
        self.assertEqual(feature[0].get("name"), "twp_job_name")

    def test_no_job_box_without_job_fields(self):
        order = self.make_quote()
        order.write({field["name"]: False for field in order._twp_header_fields()})
        tree = self.tree(self.render_quote(order))
        self.assertFalse(tree.xpath("//td[@name='twp_cx_job']"))
        self.assertEqual(len(tree.xpath("//table[@name='twp_cx_info']//td[contains(@class, 'twp_cx_gap')]")), 1)

    def test_introduction_under_the_info_row(self):
        page = self.render_quote(self.make_quote())
        intro = page.index("Here is the quote you requested.")
        self.assertLess(page.index('name="twp_cx_info"'), intro)
        self.assertLess(intro, page.index("o_main_table"))

    def test_margins(self):
        root = self.tree(self.render_quote(self.make_quote()))
        self.assertEqual(root.get("data-report-margin-top"), "30")
        self.assertEqual(root.get("data-report-header-spacing"), "30")

    def test_every_other_line_shaded(self):
        order = self.make_quote()
        order.write({"order_line": [Command.create({"product_id": self.fan.id, "product_uom_qty": 1})]})
        rows = self.product_rows(self.render_quote(order))
        self.assertEqual([("twp_cx_z" in (row.get("class") or "")) for row in rows], [False, True, False])

    def test_quantity_without_units(self):
        page = self.render_quote(self.make_quote())
        self.assertEqual(self.row(page, "TWP Bracket")[1], "2")

    def test_note_stays_in_the_table(self):
        order = self.make_quote()
        order.write({"order_line": [Command.create({
            "display_type": "line_note", "name": "TWP M10 note", "sequence": 9999,
        })]})
        page = self.render_quote(order)
        notes = self.tree(page).xpath("//table[contains(@class, 'o_main_table')]//tr[@name='tr_note']")
        self.assertIn("TWP M10 note", notes[0].text_content())

    def test_bundle_shaded_as_one_block(self):
        self.bracket.description_sale = "TWP M10 second line"
        order = self.make_order(bundle_only=True)
        # A line above the bundle is the first item, so the bundle is the second, shaded.
        order.write({"order_line": [Command.create({"product_id": self.fan.id, "product_uom_qty": 1, "sequence": 5})]})
        order.invalidate_recordset(["order_line"])  # read the lines back in sequence order
        page = self.render_quote(order)
        tree = self.tree(page)
        fan = [row for row in self.product_rows(page) if "TWP Fan" in row.text_content()][0]
        self.assertNotIn("twp_cx_z", fan.get("class") or "")
        bundle = tree.xpath("//tr[@name='twp_tr_bundle']")[0]
        self.assertIn("twp_cx_z", bundle.get("class"))
        members = [row for row in self.product_rows(page) if "twp_cx_member" in (row.get("class") or "")]
        self.assertEqual(len(members), 2)
        self.assertTrue(all("twp_cx_z" in row.get("class") for row in members))
        # A member prints its product's name only, not its description.
        self.assertIn("TWP Bracket", page)
        self.assertNotIn("TWP M10 second line", page)

    def test_confirmed_order(self):
        order = self.make_quote()
        order.action_confirm()
        tree = self.tree(self.render_quote(order))
        self.assertIn("Order", tree.xpath("//div[contains(@class, 'twp_cx_doc_title')]")[0].text_content())
        self.assertIn("Order for", tree.xpath("//td[@name='twp_cx_customer']")[0].text_content())

    def test_invoice_keeps_the_document_layout(self):
        order = self.make_quote()
        order.action_confirm()
        invoice = order._create_invoices()
        page = self.render_invoice(invoice)
        self.assertNotIn("twp_cx_header", page)
        self.assertNotIn("twp_compact", page)

    def test_pro_forma_keeps_the_document_layout(self):
        order = self.make_quote()
        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder_pro_forma", order.ids)
        self.assertNotIn("twp_cx_header", html.decode())

    def test_icon_and_contact(self):
        company = self.env.company
        company.write({"phone": "317-555-0100", "website": "https://example.com/"})
        self.assertEqual(company._twp_compact_contact(), "317-555-0100 | example.com")
        page = self.render_quote(self.make_quote())
        self.assertIn("317-555-0100 | example.com", page)

    def make_split_address_quote(self):
        """A quote whose invoicing and delivery addresses are contacts of their own."""
        billing = self.env["res.partner"].create({
            "name": "TWP Billing Desk", "type": "invoice", "parent_id": self.partner.id, "street": "1 Ledger Way",
        })
        shipping = self.env["res.partner"].create({
            "name": "TWP Job Site", "type": "delivery", "parent_id": self.partner.id, "street": "9 Dock Road",
        })
        order = self.make_quote()
        order.write({"partner_invoice_id": billing.id, "partner_shipping_id": shipping.id})
        return order

    def test_customer_box_shows_the_customer_only(self):
        order = self.make_split_address_quote()
        page = self.render_quote(order)
        customer = self.tree(page).xpath("//td[@name='twp_cx_customer']")[0].text_content()
        self.assertIn("TWP Test Customer", customer)
        for text in ("TWP Billing Desk", "1 Ledger Way", "TWP Job Site", "9 Dock Road"):
            self.assertNotIn(text, page)
        for text in ("Invoicing Address", "Shipping Address"):
            self.assertNotIn(text, page)

    def test_confirmed_order_shows_the_customer_only(self):
        order = self.make_split_address_quote()
        order.action_confirm()
        page = self.render_quote(order)
        for text in ("TWP Billing Desk", "TWP Job Site"):
            self.assertNotIn(text, page)

    def test_invoice_keeps_both_addresses(self):
        order = self.make_split_address_quote()
        order.action_confirm()
        page = self.render_invoice(order._create_invoices())
        for text in ("1 Ledger Way", "9 Dock Road"):
            self.assertIn(text, page)

    def test_no_terms_and_conditions(self):
        order = self.make_quote()
        order.note = "<p>TWP M10 terms</p>"
        self.assertNotIn("TWP M10 terms", self.render_quote(order))

    def test_document_layout_keeps_terms_and_addresses(self):
        self.env.company.twp_sale_layout = "company"
        order = self.make_split_address_quote()
        order.note = "<p>TWP M10 terms</p>"
        page = self.render_quote(order)
        for text in ("TWP M10 terms", "TWP Billing Desk", "TWP Job Site"):
            self.assertIn(text, page)
