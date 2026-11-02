from ast import literal_eval

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestBids(TransactionCase):
    """Bids built like quotes, numbered apart, kept out of Quotations until one is won."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.twp_number_orders = False
        cls.heater = cls.env["product.product"].create({"name": "TWP Bid Heater", "type": "consu", "list_price": 1000})
        Partner = cls.env["res.partner"]
        cls.bidder_a = Partner.create({"name": "TWP Bidder A"})
        cls.bidder_b = Partner.create({"name": "TWP Bidder B"})
        cls.bidder_c = Partner.create({"name": "TWP Bidder C"})
        # A team of its own, so a database's rules for its default team don't apply.
        team = cls.env["crm.team"].create({"name": "TWP Bid Team"})
        cls.opportunity = cls.env["crm.lead"].create({
            "name": "TWP Main Street School", "type": "opportunity", "team_id": team.id,
        })

    def setUp(self):
        super().setUp()
        # Numbers come from database sequences, which a test's rollback does not wind back.
        self.env["res.config.settings"].create({
            "twp_quote_prefix": "TQ", "twp_quote_padding": 4, "twp_quote_next_number": 1,
            "twp_bid_prefix": "TB", "twp_bid_padding": 4, "twp_bid_next_number": 1,
        }).execute()

    def _bid(self, partner=None, price=950.0):
        return self.env["sale.order"].with_context(default_twp_is_bid=True).create({
            "partner_id": (partner or self.bidder_a).id,
            "opportunity_id": self.opportunity.id,
            "order_line": [Command.create({"product_id": self.heater.id, "product_uom_qty": 3, "price_unit": price})],
        })

    def test_bid_takes_a_bid_number(self):
        bid = self._bid()
        self.assertEqual((bid.name, bid.twp_bid_number, bid.twp_is_bid, bid.twp_bid_status), ("TB0001", "TB0001", True, "open"))
        quote = self.env["sale.order"].create({"partner_id": self.bidder_a.id})
        self.assertEqual(quote.name, "TQ0001", "A bid spends no quote number")
        self.assertFalse(quote.twp_is_bid)

    def test_bid_settings(self):
        settings = self.env["res.config.settings"].create({})
        self.assertEqual((settings.twp_bid_prefix, settings.twp_bid_padding), ("TB", 4))
        settings.twp_bid_next_number = 40
        settings.execute()
        self.assertEqual(self._bid().name, "TB0040")

    def test_bids_stay_out_of_quotations(self):
        bid = self._bid()
        quote = self.env["sale.order"].create({"partner_id": self.bidder_a.id, "opportunity_id": self.opportunity.id})
        for xmlid in ("sale.action_quotations_with_onboarding", "sale.action_quotations", "sale.action_quotations_salesteams"):
            domain = self.env["ir.actions.actions"]._for_xml_id(xmlid)["domain"]
            found = self.env["sale.order"].search(literal_eval(domain) + [("opportunity_id", "=", self.opportunity.id)])
            self.assertEqual(found, quote, xmlid)
        self.assertEqual(self.opportunity.quotation_count, 1)
        self.assertEqual(self.opportunity.twp_bid_count, 1)
        bids = self.env["sale.order"].search(self.opportunity.action_twp_view_bids()["domain"])
        self.assertEqual(bids, bid)

    def test_bids_search_on_their_own(self):
        order_search = self.env["sale.order"].get_views([(False, "search")])["views"]["search"]["arch"]
        self.assertNotIn("twp_open_bids", order_search, "Quotations and Orders keep Sales' search")
        view = self.env.ref("twp_bids.view_bid_search")
        self.assertEqual(self.env.ref("twp_bids.action_bids").search_view_id, view)
        bid_search = self.env["sale.order"].get_views([(view.id, "search")])["views"]["search"]["arch"]
        self.assertIn("twp_open_bids", bid_search)

    def test_bid_is_titled_and_mailed_as_a_bid(self):
        bid = self._bid()
        self.assertEqual(bid.type_name, "Bid")
        self.assertEqual(bid._find_mail_template(), self.env.ref("twp_bids.email_template_bid"))
        self.assertTrue(bid._get_report_base_filename().startswith("Bid - TB0001"))

    def test_bid_cannot_be_confirmed_or_accepted(self):
        bid = self._bid()
        bid.require_signature = True
        self.assertFalse(bid._has_to_be_signed())
        with self.assertRaises(UserError):
            bid.action_confirm()

    def test_sending_stamps_the_bid(self):
        bid = self._bid()
        bid.action_quotation_sent()
        self.assertEqual(bid.state, "sent")
        self.assertTrue(bid.twp_bid_sent_date)

    def test_copy_to_customers(self):
        bid = self._bid()
        bid.payment_term_id = self.env.ref("account.account_payment_term_30days")
        wizard = Form(self.env["twp.bid.copy"].with_context(default_bid_id=bid.id))
        wizard.partner_ids.add(self.bidder_b)
        wizard.partner_ids.add(self.bidder_c)
        wizard.save().action_apply()
        copies = self.env["sale.order"].search([("twp_bid_source_id", "=", bid.id)])
        self.assertEqual(copies.partner_id, self.bidder_b | self.bidder_c)
        self.assertEqual(sorted(copies.mapped("name")), ["TB0002", "TB0003"])
        for copy in copies:
            self.assertTrue(copy.twp_is_bid)
            self.assertEqual(copy.opportunity_id, self.opportunity)
            self.assertEqual(copy.partner_invoice_id, copy.partner_id)
            self.assertEqual(copy.order_line.price_unit, 950.0, "The bid's own price, not the list price")
            self.assertEqual(copy.amount_untaxed, bid.amount_untaxed)
            self.assertEqual(copy.payment_term_id, bid.payment_term_id, "No terms of their own: the bid's")
        self.assertEqual(bid.twp_bid_copy_count, 2)
        for copy in copies:
            self.assertIn(f"Copied from {bid.name}", " ".join(copy.message_ids.mapped("body")))

    def _duplicate(self, bid, partner, opportunity=None, user=None):
        wizard = Form(self.env["twp.bid.copy"].with_user(user or self.env.user).with_context(default_bid_id=bid.id))
        wizard.partner_ids.add(partner)
        if opportunity:
            wizard.opportunity_id = opportunity
        wizard.save().action_apply()
        return self.env["sale.order"].search([("twp_bid_source_id", "=", bid.id), ("partner_id", "=", partner.id)])

    def test_duplicate_is_edited_on_its_own(self):
        bid = self._bid()
        first = self._duplicate(bid, self.bidder_b)
        second = self._duplicate(bid, self.bidder_c)
        line = first.order_line
        first.write({"order_line": [
            Command.update(line.id, {"price_unit": 1200.0, "product_uom_qty": 5, "name": "Changed on the copy"}),
            Command.create({"product_id": self.heater.id, "product_uom_qty": 1, "price_unit": 10.0}),
        ]})
        self.assertEqual(len(first.order_line), 2)
        for order in (bid, second):
            self.assertEqual(len(order.order_line), 1)
            self.assertEqual((order.order_line.price_unit, order.order_line.product_uom_qty), (950.0, 3))
            self.assertNotEqual(order.order_line.name, "Changed on the copy")
        self.assertFalse(first.order_line & (bid.order_line | second.order_line))

    def test_a_lost_bid_is_duplicated_as_an_open_bid(self):
        bid = self._bid()
        bid.action_twp_bid_lost()
        arch = self.env["sale.order"].get_view(self.env.ref("sale.view_order_form").id, "form")["arch"]
        self.assertIn('invisible="not twp_is_bid or not id"', arch.split('name="action_twp_copy_to_customers"')[1][:80])
        copy = self._duplicate(bid, self.bidder_b)
        self.assertEqual((copy.twp_is_bid, copy.twp_bid_status, copy.state), (True, "open", "draft"))
        self.assertEqual((bid.twp_bid_status, bid.state), ("lost", "cancel"), "The lost bid stays lost")

    def test_duplicate_bid_from_the_project(self):
        earlier = self.env["crm.lead"].create({
            "name": "TWP Oak Street Gym", "type": "opportunity", "team_id": self.opportunity.team_id.id,
        })
        old_bid = self._bid()
        old_bid.opportunity_id = earlier
        action = self.opportunity.action_twp_duplicate_bid()
        self.assertFalse(action["context"]["default_bid_id"], "No bid on this project yet")
        wizard = Form(self.env["twp.bid.copy"].with_context(action["context"]))
        wizard.bid_id = old_bid
        self.assertEqual(wizard.opportunity_id, self.opportunity, "The project it was opened from")
        wizard.partner_ids.add(self.bidder_b)
        wizard.save().action_apply()
        copy = self.env["sale.order"].search([("twp_bid_source_id", "=", old_bid.id)])
        self.assertEqual((copy.opportunity_id, copy.partner_id, copy.twp_job_name), (self.opportunity, self.bidder_b, self.opportunity.name))
        self.assertEqual(self.opportunity.action_twp_duplicate_bid()["context"]["default_bid_id"], copy.id, "Then its latest bid")

    def test_duplicate_onto_another_project(self):
        bid = self._bid()
        other = self.env["crm.lead"].create({
            "name": "TWP Elm Street Library", "type": "opportunity", "team_id": self.opportunity.team_id.id,
        })
        wizard = Form(self.env["twp.bid.copy"].with_context(default_bid_id=bid.id))
        self.assertEqual(wizard.opportunity_id, self.opportunity, "The bid's own project by default")
        self.assertEqual(wizard.already_bid_ids.ids, self.bidder_a.ids)
        wizard.opportunity_id = other
        self.assertFalse(wizard.already_bid_ids.ids)
        copy = self._duplicate(bid, self.bidder_b, opportunity=other)
        self.assertEqual((copy.opportunity_id, copy.twp_job_name), (other, other.name))
        self.assertEqual(copy.twp_bid_source_id, bid)
        bid.action_twp_bid_won()
        self.assertEqual(copy.twp_bid_status, "open", "A bid on another project doesn't compete")

    def test_duplicate_keeps_allowed_alternatives(self):
        self.env.company.twp_allow_options_by = "managers"
        # Sees every bid, but is no Sales administrator.
        rep = new_test_user(self.env, login="twp_bid_rep", groups="sales_team.group_sale_salesman_all_leads")
        bid = self._bid()
        bid.twp_allow_options = True
        copy = self._duplicate(bid.with_user(rep), self.bidder_b, user=rep)
        self.assertTrue(copy.twp_allow_options, "Approved on the bid it copies")
        self.assertFalse(bid.copy().twp_allow_options, "Duplicate on its own still asks again")
        with self.assertRaises(UserError):
            copy.with_user(rep).copy({"twp_allow_options": True})

    def test_won_bid_becomes_a_quotation_and_beats_the_others(self):
        bid_a = self._bid(self.bidder_a)
        bid_b = self._bid(self.bidder_b, price=990.0)
        bid_a.action_quotation_sent()
        bid_a.action_twp_bid_won()
        self.assertEqual((bid_a.name, bid_a.twp_bid_number), ("TQ0001", "TB0001"))
        self.assertEqual((bid_a.twp_is_bid, bid_a.twp_bid_status, bid_a.state), (False, "won", "draft"))
        self.assertEqual(bid_a.type_name, "Quotation")
        self.assertEqual((bid_b.twp_bid_status, bid_b.state), ("lost", "cancel"))
        self.assertEqual(self.opportunity.quotation_count, 1)
        self.assertEqual(self.opportunity.twp_bid_count, 2)
        bid_a.action_confirm()
        self.assertEqual(bid_a.state, "sale")

    def test_lost_bid_reopens(self):
        bid = self._bid()
        bid.action_twp_bid_lost()
        self.assertEqual((bid.twp_bid_status, bid.state), ("lost", "cancel"))
        bid.action_draft()
        self.assertEqual((bid.twp_bid_status, bid.state, bid.twp_is_bid), ("open", "draft", True))

    def test_a_lost_bid_can_still_win(self):
        bid = self._bid()
        bid.action_twp_bid_lost()
        bid._twp_make_quotation()
        self.assertEqual((bid.twp_bid_status, bid.state, bid.twp_is_bid), ("won", "draft", False))

    def test_new_bid_from_the_opportunity(self):
        action = self.opportunity.action_twp_new_bid()
        context = action["context"]
        self.assertTrue(context["default_twp_is_bid"])
        self.assertNotIn("default_partner_id", context)
        form = Form(self.env["sale.order"].with_context(context))
        form.partner_id = self.bidder_a
        bid = form.save()
        self.assertTrue(bid.twp_is_bid)
        self.assertEqual((bid.opportunity_id, bid.twp_job_name), (self.opportunity, self.opportunity.name))

    def test_bid_options_are_not_chosen_online(self):
        self.env.company.twp_portal_choice = True
        bid = self._bid()
        bid.write({"order_line": [
            Command.create({
                "display_type": "line_section", "name": "Option 1",
                "twp_option_mode": "alternative", "sequence": 50,
            }),
            Command.create({"product_id": self.heater.id, "product_uom_qty": 1, "sequence": 51}),
        ]})
        option = bid.order_line.filtered(lambda line: line.name == "Option 1")
        self.assertFalse(bid._twp_customer_can_choose())
        option.with_context(import_file=True).twp_option_chosen = True
        self.assertFalse(bid._twp_unrecorded_choices(), "A bid goes out as the bidder prices it")

