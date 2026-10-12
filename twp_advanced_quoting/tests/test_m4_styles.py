from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval, time

from odoo.addons.twp_advanced_quoting import SALE_REPORT_NAME, post_init_hook, uninstall_hook

from .test_m1_documents import DocumentCase


class StyleCase(DocumentCase):
    """Two styles matched by tag: Distributor gets an itemized one, Contractor a grouped Proposal.

    Customers with neither tag get the shipped Grouped style, the company default.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tag = cls.env["res.partner.category"]
        cls.distributor_tag = Tag.create({"name": "TWP M4 Distributor"})
        cls.contractor_tag = Tag.create({"name": "TWP M4 Contractor"})
        cls.grouped = cls.env.ref("twp_advanced_quoting.document_style_grouped")
        Style = cls.env["twp.document.style"]
        cls.itemized_style = Style.create({
            "name": "TWP M4 Distributor",
            "sequence": 1,
            "structure": "itemized",
            "tag_ids": [Command.set(cls.distributor_tag.ids)],
            "discount_column": "net",
            "show_line_numbers": True,
        })
        cls.proposal_style = Style.create({
            "name": "TWP M4 Contractor",
            "sequence": 2,
            "structure": "grouped",
            "title_word": "Proposal",
            "tag_ids": [Command.set(cls.contractor_tag.ids)],
        })
        cls.env.company.twp_default_document_style_id = cls.grouped
        Partner = cls.env["res.partner"]
        cls.distributor = Partner.create({
            "name": "TWP M4 Hoeing",
            "is_company": True,
            "category_id": [Command.set(cls.distributor_tag.ids)],
        })
        cls.distributor_buyer = Partner.create({"name": "TWP M4 Buyer", "parent_id": cls.distributor.id})
        cls.contractor = Partner.create({
            "name": "TWP M4 Contractor Co",
            "is_company": True,
            "category_id": [Command.set(cls.contractor_tag.ids)],
        })
        cls.rep = new_test_user(cls.env, login="twp_m4_rep", groups="sales_team.group_sale_salesman")
        cls.admin = new_test_user(cls.env, login="twp_m4_admin", groups="sales_team.group_sale_manager")

    def plain_quote(self, partner, **values):
        """Two priced lines, nothing hidden: a quote any style allows."""
        return self.env["sale.order"].create({
            "partner_id": partner.id,
            "twp_job_name": "Main Street School",
            "twp_ship_via": "Best Way",
            "twp_freight": "Prepaid and Add",
            "twp_introduction": "<p>Here is the quote you requested.</p>",
            "order_line": [
                Command.create({"product_id": self.heater.id, "product_uom_qty": 1}),
                Command.create({"product_id": self.bracket.id, "product_uom_qty": 2, "discount": 10}),
            ],
            **values,
        })

    def options_quote(self, partner, **values):
        """A plain heater, and two alternatives with a line each."""
        return self.env["sale.order"].create({
            "partner_id": partner.id,
            **values,
            "order_line": [
                Command.create({"product_id": self.heater.id, "product_uom_qty": 1, "sequence": 1}),
                Command.create({
                    "display_type": "line_section",
                    "name": "Option 1",
                    "twp_option_mode": "alternative",
                    "sequence": 10,
                }),
                Command.create({"product_id": self.option_one.id, "product_uom_qty": 1, "sequence": 11}),
                Command.create({
                    "display_type": "line_section",
                    "name": "Option 2",
                    "twp_option_mode": "alternative",
                    "sequence": 20,
                }),
                Command.create({"product_id": self.option_two.id, "product_uom_qty": 1, "sequence": 21}),
            ],
        })


@tagged("post_install", "-at_install")
class TestStyleMatching(StyleCase, TransactionCase):
    """A quote takes its style from its customer's tags."""

    def test_shipped_styles(self):
        itemized = self.env.ref("twp_advanced_quoting.document_style_itemized")
        self.assertEqual(itemized.structure, "itemized")
        self.assertEqual(itemized.discount_column, "net")
        self.assertEqual(self.grouped.structure, "grouped")
        self.assertEqual(self.grouped.order_title_word, "Order")
        # A company with no default gets Grouped when the module is installed.
        company = self.env["res.company"].create({"name": "TWP M4 Company"})
        company.twp_default_document_style_id = False
        post_init_hook(self.env)
        self.assertEqual(company.twp_default_document_style_id, self.grouped)

    def test_tag_on_the_company_sets_the_style(self):
        self.assertEqual(self.plain_quote(self.distributor_buyer).twp_document_style_id, self.itemized_style)
        self.assertEqual(self.plain_quote(self.contractor).twp_document_style_id, self.proposal_style)

    def test_untagged_customer_gets_the_default(self):
        self.assertEqual(self.plain_quote(self.partner).twp_document_style_id, self.grouped)

    def test_first_style_in_order_wins(self):
        both = self.env["res.partner"].create({
            "name": "TWP M4 Both",
            "category_id": [Command.set((self.distributor_tag | self.contractor_tag).ids)],
        })
        self.assertEqual(self.plain_quote(both).twp_document_style_id, self.itemized_style)
        self.itemized_style.sequence = 50
        self.assertEqual(self.plain_quote(both).twp_document_style_id, self.proposal_style)

    def test_changing_the_customer_matches_again(self):
        order = self.plain_quote(self.partner)
        order.partner_id = self.distributor
        self.assertEqual(order.twp_document_style_id, self.itemized_style)
        order.partner_id = self.contractor
        self.assertEqual(order.twp_document_style_id, self.proposal_style)

    def test_template_style_when_no_tag_matches(self):
        template = self.env["sale.order.template"].create({
            "name": "TWP M4 Template",
            "twp_document_style_id": self.proposal_style.id,
        })
        untagged = self.plain_quote(self.partner, sale_order_template_id=template.id)
        self.assertEqual(untagged.twp_document_style_id, self.proposal_style)
        # The customer's tag wins over the template, so the standard holds.
        distributor = self.plain_quote(self.distributor, sale_order_template_id=template.id)
        self.assertEqual(distributor.twp_document_style_id, self.itemized_style)


@tagged("post_install", "-at_install")
class TestStyleLock(StyleCase, TransactionCase):
    """Only a Sales administrator changes a quote's style, unless Settings lets salespeople."""

    def test_salesperson_keeps_the_matched_style(self):
        order = self.plain_quote(self.contractor, user_id=self.rep.id).with_user(self.rep)
        self.assertFalse(order.twp_can_change_style)
        with self.assertRaises(UserError):
            order.twp_document_style_id = self.grouped
        # Changing the customer re-matches the style; that is not a change by hand.
        order.partner_id = self.distributor
        self.assertEqual(order.twp_document_style_id, self.itemized_style)

    def test_salesperson_cannot_create_with_another_style(self):
        with self.assertRaises(UserError):
            self.env["sale.order"].with_user(self.rep).create({
                "partner_id": self.distributor.id,
                "twp_document_style_id": self.grouped.id,
            })

    def test_administrator_changes_the_style(self):
        order = self.plain_quote(self.contractor, user_id=self.admin.id).with_user(self.admin)
        self.assertTrue(order.twp_can_change_style)
        order.twp_document_style_id = self.grouped
        self.assertEqual(order.twp_document_style_id, self.grouped)

    def test_setting_lets_salespeople_change_it(self):
        self.env.company.twp_reps_change_style = True
        order = self.plain_quote(self.contractor, user_id=self.rep.id).with_user(self.rep)
        self.assertTrue(order.twp_can_change_style)
        order.twp_document_style_id = self.grouped
        self.assertEqual(order.twp_document_style_id, self.grouped)


@tagged("post_install", "-at_install")
class TestItemizedRule(StyleCase, TransactionCase):
    """An itemized quote prints every line with its price, enforced on the server."""

    def test_bundles_and_options_are_saved_with_a_warning(self):
        order = self.make_order()
        order.partner_id = self.distributor
        self.assertEqual(order.twp_document_style_id, self.itemized_style)
        issues = order.twp_style_issues
        for text in ("Heater package is a bundle.", "Option 1 is an alternative.",
                     "HVLS fan is an add-on.", "is hidden on documents."):
            self.assertIn(text, issues)

    def test_cannot_confirm_send_print_or_sign(self):
        order = self.make_order()
        order.partner_id = self.distributor
        with self.assertRaisesRegex(UserError, "Heater package is a bundle"):
            order.action_confirm()
        self.assertEqual(order.state, "draft")
        with self.assertRaises(UserError):
            order.action_quotation_send()
        with self.assertRaises(UserError):
            self.env["ir.actions.report"]._render_qweb_pdf("sale.action_report_saleorder", order.ids)
        self.assertFalse(order._has_to_be_signed())
        self.assertFalse(order._has_to_be_paid())

    def test_hidden_prices_and_sections_are_issues(self):
        order = self.plain_quote(self.distributor)
        self.assertFalse(order.twp_style_issues)
        order.order_line.filtered(lambda line: line.product_id == self.heater).twp_hide_price = True
        self.assertIn("hides its price.", order.twp_style_issues)
        order.order_line = [Command.create({"display_type": "line_section", "name": "Fans", "collapse_prices": True})]
        self.assertIn("Fans hides its prices.", order.twp_style_issues)

    def test_a_clean_itemized_quote_prints_and_confirms(self):
        order = self.plain_quote(self.distributor)
        self.assertFalse(order.twp_style_issues)
        self.env["ir.actions.report"]._render_qweb_pdf("sale.action_report_saleorder", order.ids)
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_grouped_quote_allows_everything(self):
        order = self.make_order()
        order.partner_id = self.contractor
        self.assertFalse(order.twp_style_issues)
        self.env["ir.actions.report"]._render_qweb_pdf("sale.action_report_saleorder", order.ids)

    def test_allow_alternatives_override(self):
        """D7: an itemized quote can carry alternatives, every line still priced."""
        order = self.options_quote(self.distributor)
        self.assertIn("Option 2 is an alternative.", order.twp_style_issues)
        order.twp_allow_options = True
        self.assertFalse(order.twp_style_issues)
        self.assertIn("Alternatives and add-ons allowed", order.message_ids[0].body)
        # Still itemized: an option's lines keep their prices.
        order.order_line.filtered(lambda line: line.product_id == self.option_two).twp_hide_price = True
        self.assertIn("hides its price.", order.twp_style_issues)

    def test_who_allows_alternatives(self):
        order = self.options_quote(self.distributor, user_id=self.rep.id)
        with self.assertRaises(UserError):
            order.with_user(self.rep).twp_allow_options = True
        order.with_user(self.admin).twp_allow_options = True
        self.assertTrue(order.twp_allow_options)
        self.env.company.twp_allow_options_by = "everyone"
        other = self.options_quote(self.distributor, user_id=self.rep.id)
        other.with_user(self.rep).twp_allow_options = True
        self.assertTrue(other.twp_allow_options)


@tagged("post_install", "-at_install")
class TestStylePrinting(StyleCase, TransactionCase):
    """The style's title, file name, columns and header fields on the quote PDF."""

    def test_title_word_and_order_title(self):
        order = self.plain_quote(self.contractor)
        self.assertEqual(order.type_name, "Proposal")
        self.assertIn("Proposal #", " ".join(self.render_quote(order).split()))
        order.action_confirm()
        self.assertEqual(order.type_name, "Order")
        self.assertIn("Order #", " ".join(self.render_quote(order).split()))
        self.proposal_style.order_title_word = "Sales Order"
        order.invalidate_recordset(["type_name"])
        self.assertEqual(order.type_name, "Sales Order")

    def test_no_title_word_keeps_odoo_title(self):
        order = self.plain_quote(self.distributor)
        self.assertEqual(order.type_name, "Quotation")
        self.assertIn("Quotation #", " ".join(self.render_quote(order).split()))

    def test_budget_estimate(self):
        order = self.plain_quote(self.contractor)
        self.assertTrue(order._has_to_be_signed())
        order.twp_is_estimate = True
        self.assertEqual(order.type_name, "Estimate")
        page = " ".join(self.render_quote(order).split())
        self.assertIn("Estimate #", page)
        self.assertIn("Budget pricing", page)
        # An estimate is budget pricing: the customer can't accept it online.
        self.assertFalse(order._has_to_be_signed())
        order.action_confirm()
        page = " ".join(self.render_quote(order).split())
        self.assertIn("Order #", page)
        self.assertNotIn("Budget pricing", page)

    def test_file_name(self):
        """D14: title, number and Job Name, the same from the Print menu, the email and the portal."""
        order = self.plain_quote(self.contractor)
        expected = f"Proposal - {order.name} - Main Street School"
        self.assertEqual(order._get_report_base_filename(), expected)
        report = self.env.ref("sale.action_report_saleorder")
        self.assertEqual(safe_eval(report.print_report_name, {"object": order, "time": time}), expected)
        order.twp_job_name = False
        self.assertEqual(order._get_report_base_filename(), f"Proposal - {order.name}")

    def test_uninstall_puts_odoo_file_name_back(self):
        report = self.env.ref("sale.action_report_saleorder")
        uninstall_hook(self.env)
        self.assertEqual(report.print_report_name, SALE_REPORT_NAME)
        order = self.plain_quote(self.contractor)
        self.assertEqual(safe_eval(report.print_report_name, {"object": order, "time": time}), f"Quotation - {order.name}")

    def test_net_prices(self):
        """D9: a distributor sees each unit price net, with no discount column."""
        page = self.render_quote(self.plain_quote(self.distributor))
        self.assertNotIn("Disc.%", self.headers(page))
        bracket = " ".join(self.row(page, "TWP Bracket"))
        self.assertIn("18.00", bracket)
        self.assertNotIn("20.00", bracket)
        self.assertIn("36.00", bracket)

    def test_discount_column_when_the_style_shows_it(self):
        page = self.render_quote(self.plain_quote(self.contractor))
        self.assertIn("Disc.%", self.headers(page))
        self.assertIn("20.00", " ".join(self.row(page, "TWP Bracket")))

    def test_taxes_column(self):
        order = self.plain_quote(self.contractor)
        self.assertIn("Taxes", self.headers(self.render_quote(order)))
        self.proposal_style.show_taxes = False
        self.assertNotIn("Taxes", self.headers(self.render_quote(order)))

    def test_header_fields_the_style_prints(self):
        order = self.plain_quote(self.contractor)
        self.proposal_style.write({"print_freight": False, "print_introduction": False})
        page = self.render_quote(order)
        self.assertIn("Best Way", page)
        self.assertIn("Main Street School", page)
        self.assertNotIn("Prepaid and Add", page)
        self.assertNotIn("Here is the quote you requested.", page)


@tagged("post_install", "-at_install")
class TestStylePortal(StyleCase, HttpCase):
    """The customer's online quote follows the style."""

    def portal(self, order, query=""):
        order._portal_ensure_token()
        return self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}{query}")

    def test_net_prices_online(self):
        response = self.portal(self.plain_quote(self.distributor))
        self.assertEqual(response.status_code, 200)
        bracket = " ".join(self.row(response.text, "TWP Bracket"))
        self.assertIn("18.00", bracket)
        self.assertNotIn("20.00", bracket)
        self.assertNotIn("Your advantage", response.text)

    def test_estimate_online(self):
        order = self.plain_quote(self.contractor, twp_is_estimate=True)
        page = " ".join(self.portal(order).text.split())
        self.assertIn(f"Estimate - <em>{order.name}</em>", page)
        self.assertIn("Budget pricing", page)

    def test_download_file_name(self):
        order = self.plain_quote(self.contractor)
        response = self.portal(order, "&report_type=pdf&download=true")
        self.assertEqual(response.status_code, 200)
        expected = f"Proposal_{order.name}_Main_Street_School.pdf"
        self.assertIn(expected, response.headers.get("Content-Disposition", ""))
