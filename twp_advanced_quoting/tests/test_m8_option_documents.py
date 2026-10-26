import base64

from lxml import html as lxml_html

from odoo.tests import HttpCase, TransactionCase, tagged

from .test_m3_options import OptionCase


class OptionBlockCase(OptionCase):
    """Options set apart on the quote: a tag, a block, Choose one and OR, the note by the amount."""

    def row_classes(self, page, text):
        """The classes of the table row that mentions `text`."""
        tree = lxml_html.fromstring(page)
        for tr in tree.iter("tr"):
            if text in tr.text_content() and not tr.xpath(".//tr"):
                return set((tr.get("class") or "").split())
        return None

    def texts_in_order(self, page):
        tree = lxml_html.fromstring(page)
        return [" ".join(tr.text_content().split()) for tr in tree.iter("tr") if not tr.xpath(".//tr")]

    def check_open_quote(self, page):
        self.assertTrue({"twp_opt", "twp_opt_head", "twp_opt_open"} <= self.row_classes(page, "Option 1"))
        self.assertTrue({"twp_opt", "twp_opt_member", "twp_opt_open"} <= self.row_classes(page, "TWP Option One"))
        self.assertTrue({"twp_opt", "twp_opt_head"} <= self.row_classes(page, "HVLS fan"))
        self.assertNotIn("twp_opt", self.row_classes(page, "Heater package"))
        self.assertNotIn("twp_opt", self.row_classes(page, "TWP Bracket"))
        self.assertIn("Alternative", " ".join(self.row(page, "Option 1")))
        self.assertIn("Add-on", " ".join(self.row(page, "HVLS fan")))
        self.assertIn("Not included in the total", " ".join(self.row(page, "Option 2")))
        # Choose one over the set, OR between its alternatives, nothing over the add-on.
        texts = self.texts_in_order(page)
        choose = texts.index("Choose one")
        option_one = next(i for i, text in enumerate(texts) if "Option 1" in text)
        either = texts.index("or")
        option_two = next(i for i, text in enumerate(texts) if "Option 2" in text)
        self.assertEqual(choose + 1, option_one)
        self.assertTrue(option_one < either < option_two)
        self.assertEqual(texts.count("or"), 1)


@tagged("post_install", "-at_install")
class TestOptionBlocks(OptionBlockCase, TransactionCase):

    def test_quote(self):
        self.check_open_quote(self.render_quote(self.make_order()))

    def test_chosen(self):
        order = self.make_order()
        self.section(order, "Option 2").twp_option_chosen = True
        page = self.render_quote(order)
        self.assertTrue({"twp_opt_head", "twp_opt_chosen"} <= self.row_classes(page, "Option 2"))
        self.assertTrue({"twp_opt_member", "twp_opt_chosen"} <= self.row_classes(page, "TWP Option Two"))
        self.assertIn("Chosen", " ".join(self.row(page, "Option 2")))
        self.assertIn("twp_opt_open", self.row_classes(page, "Option 1"))

    def test_lone_alternative_has_no_or(self):
        order = self.make_order()
        self.section(order, "Option 2").twp_option_group = "Another set"
        page = self.render_quote(order)
        self.assertNotIn("Choose one", self.texts_in_order(page))
        self.assertNotIn("or", self.texts_in_order(page))
        self.assertIn("Alternative", " ".join(self.row(page, "Option 2")))

    def test_confirmed_order_is_plain(self):
        order = self.make_order()
        self.section(order, "Option 2").twp_option_chosen = True
        order.action_confirm()
        page = self.render_quote(order)
        self.assertNotIn("twp_opt", page)
        self.assertNotIn("twp_badge", page)
        self.assertNotIn("Choose one", page)

    def test_colours_come_from_the_document_layout(self):
        self.env.company.primary_color = "#5e4766"
        styles = base64.b64decode(self.env["res.company"]._get_asset_style_b64()).decode()
        block = styles[styles.index(f".o_company_{self.env.company.id}_layout"):]
        self.assertIn(".twp_opt_chosen", block)
        self.assertIn("border-left-color: #5e4766", block)
        # And Odoo's own stylesheet carries it, rebuilt when the layout changed.
        asset = self.env.ref("web.asset_styles_company_report")
        self.assertIn("#5e4766", base64.b64decode(asset.datas).decode())


@tagged("post_install", "-at_install")
class TestOptionBlocksPortal(OptionBlockCase, HttpCase):

    def test_portal(self):
        order = self.make_order()
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        self.check_open_quote(response.text)
