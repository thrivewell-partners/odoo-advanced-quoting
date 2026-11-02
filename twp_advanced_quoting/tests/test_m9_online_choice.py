import json

from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_m3_options import OptionCase

# A 1 x 1 PNG, for a signature on the online quote.
SIGNATURE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class ChoiceCase(OptionCase):
    """M9: the customer chooses online, and the salesperson can record the choice for them."""

    def setUp(self):
        super().setUp()
        self.env.company.twp_portal_choice = True

    def notes(self, order):
        return order.message_ids.filtered(lambda m: m.subtype_id == self.env.ref("mail.mt_note"))

    def note_bodies(self, order):
        return " | ".join(self.notes(order).mapped("body"))


@tagged("post_install", "-at_install")
class TestRecordedChoice(ChoiceCase, TransactionCase):
    """A pick made by the salesperson is recorded as the customer's; one nobody made is not."""

    def test_staff_pick_is_the_customers(self):
        order = self.make_order()
        option_one = self.section(order, "Option 1")
        option_one.twp_option_chosen = True
        self.assertTrue(option_one.twp_customer_chose)
        self.assertIn(f"Recorded for the customer by {self.env.user.name}: Chose Option 1.", self.note_bodies(order))
        self.assertFalse(order._twp_unrecorded_choices())

    def test_switching_clears_the_other(self):
        order = self.make_order()
        option_one, option_two = self.section(order, "Option 1"), self.section(order, "Option 2")
        option_one.twp_option_chosen = True
        option_two.twp_option_chosen = True
        self.assertFalse(option_one.twp_option_chosen)
        self.assertFalse(option_one.twp_customer_chose)
        self.assertTrue(option_two.twp_customer_chose)

    def test_addon_notes(self):
        order = self.make_order()
        fan = self.section(order, "HVLS fan")
        fan.twp_option_chosen = True
        fan.twp_option_chosen = False
        bodies = self.note_bodies(order)
        self.assertIn("Added HVLS fan.", bodies)
        self.assertIn("Removed HVLS fan.", bodies)

    def test_unchanged_writes_no_note(self):
        order = self.make_order()
        self.section(order, "HVLS fan").twp_option_chosen = False
        self.assertFalse(self.notes(order).filtered(lambda m: "HVLS fan" in (m.body or "")))

    def test_duplicate_cannot_be_sent_with_the_pick(self):
        order = self.make_order()
        self.section(order, "Option 1").twp_option_chosen = True
        order.action_quotation_send()
        copy = order.copy()
        option_one = self.section(copy, "Option 1")
        self.assertTrue(option_one.twp_option_chosen)
        self.assertFalse(option_one.twp_customer_chose)
        self.assertEqual(copy._twp_unrecorded_choices(), option_one)
        with self.assertRaises(UserError):
            copy.action_quotation_send()
        with self.assertRaises(UserError):
            copy.action_quotation_sent()
        # Marked again, it is the customer's choice and goes out.
        option_one.twp_option_chosen = False
        option_one.twp_option_chosen = True
        copy.action_quotation_send()

    def test_unpicked_and_preadded_addon_can_be_sent(self):
        order = self.make_order()
        order.action_quotation_send()
        self.section(order, "HVLS fan").twp_option_chosen = True
        order.action_quotation_sent()
        self.assertEqual(order.state, "sent")

    def test_import_is_not_the_customers(self):
        order = self.make_order()
        option_one = self.section(order, "Option 1")
        option_one.with_context(import_file=True).twp_option_chosen = True
        self.assertFalse(option_one.twp_customer_chose)
        with self.assertRaises(UserError):
            order.action_quotation_send()
        self.assertNotIn("Recorded for the customer", self.note_bodies(order), "An import records nobody's choice")

    def test_phone_order_confirms_without_the_portal(self):
        order = self.make_order()
        self.section(order, "Option 2").twp_option_chosen = True
        self.section(order, "HVLS fan").twp_option_chosen = True
        self.assertFalse(order.access_token and order.state == "sent")
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertEqual(self.line(order, self.option_two).product_uom_qty, 1.0)
        self.assertEqual(self.line(order, self.option_one).product_uom_qty, 0.0)
        self.assertEqual(order.amount_untaxed, 7100.0)

    def test_wizard_records_the_choice(self):
        order = self.make_order()
        wizard = self.env["twp.option.choice"].browse(self.confirm_from_button(order)["res_id"])
        wizard.line_ids.filtered(lambda l: l.name == "Option 2").chosen = True
        wizard.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertTrue(self.section(order, "Option 2").twp_customer_chose)
        self.assertIn("Recorded for the customer by", self.note_bodies(order))

    def test_salesperson_records_with_the_setting_off(self):
        self.env.company.twp_portal_choice = False
        order = self.make_order()
        self.assertFalse(order._twp_customer_can_choose())
        self.section(order, "Option 2").twp_option_chosen = True
        self.assertTrue(self.section(order, "Option 2").twp_customer_chose)
        order.action_quotation_send()

    def test_customer_can_choose(self):
        order = self.make_order()
        self.assertTrue(order._twp_customer_can_choose())
        self.assertFalse(self.make_order(bundle_only=True)._twp_customer_can_choose())
        self.env.company.twp_portal_choice = False
        self.assertFalse(order._twp_customer_can_choose())


@tagged("post_install", "-at_install")
class TestOnlineChoice(ChoiceCase, HttpCase):
    """The customer's controls on the online quote, and the route behind them."""

    def setUp(self):
        super().setUp()
        self.order = self.make_order()
        self.order.twp_document_style_id = self.options_style
        self.order._portal_ensure_token()

    def portal(self, order=None):
        order = order or self.order
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        return response.text

    def choose(self, section, chosen=True, order=None, token=None):
        order = order or self.order
        response = self.url_open(
            f"/my/orders/{order.id}/twp_option",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {
                "access_token": order.access_token if token is None else token,
                "line_id": section.id,
                "chosen": chosen,
            }}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json().get("result")

    def test_controls_follow_the_setting(self):
        page = self.portal()
        self.assertEqual(page.count("Choose this option"), 2)
        self.assertIn(">Add</button>", page)
        self.assertIn("Choose one in each set below, then accept.", page)
        self.env.company.twp_portal_choice = False
        page = self.portal()
        self.assertNotIn("twp_option_choose", page)
        self.assertIn("Let us know which you would like", page)
        self.assertEqual(self.choose(self.section(self.order, "Option 2")), {"error": "refused"})
        self.assertFalse(self.section(self.order, "Option 2").twp_option_chosen)

    def test_customer_chooses_an_alternative(self):
        option_two = self.section(self.order, "Option 2")
        self.assertFalse(self.order._has_to_be_signed())
        self.assertEqual(self.choose(option_two), {"success": True})
        self.assertTrue(option_two.twp_option_chosen)
        self.assertTrue(option_two.twp_customer_chose)
        self.assertEqual(self.order.amount_untaxed, 6600.0)
        self.assertTrue(self.order._has_to_be_signed())
        note = self.notes(self.order).filtered(lambda m: "Chose Option 2" in (m.body or ""))
        self.assertEqual(note.author_id, self.partner)
        self.assertNotIn("Recorded for the customer", note.body)
        tracked = self.order.message_ids.filtered(lambda m: m.tracking_value_ids)
        self.assertTrue(tracked)
        self.assertEqual(tracked.author_id, self.partner, "The total's change is the customer's too")
        page = self.portal()
        self.assertIn("Your choice", page)
        self.assertEqual(page.count("Choose this option"), 1)
        self.assertNotIn("twp_needs_choice", page)

    def test_customer_adds_and_removes_an_addon(self):
        fan = self.section(self.order, "HVLS fan")
        self.choose(fan)
        self.assertTrue(fan.twp_option_chosen)
        self.assertEqual(self.order.amount_untaxed, 6800.0)
        self.assertIn(">Remove</button>", self.portal())
        self.choose(fan, chosen=False)
        self.assertFalse(fan.twp_option_chosen)
        self.assertEqual(self.order.amount_untaxed, 6300.0)
        bodies = self.note_bodies(self.order)
        self.assertIn("Added HVLS fan.", bodies)
        self.assertIn("Removed HVLS fan.", bodies)

    def test_refused_and_unchanged(self):
        option_two = self.section(self.order, "Option 2")
        other = self.make_order()
        other._portal_ensure_token()
        self.assertEqual(self.choose(option_two, token="wrong"), {"error": "invalid"})
        self.assertEqual(self.choose(self.section(other, "Option 2")), {"error": "refused"})
        self.assertEqual(self.choose(self.section(self.order, "Heater package")), {"error": "refused"})
        self.assertFalse(option_two.twp_option_chosen)
        self.assertFalse(self.section(other, "Option 2").twp_option_chosen)
        # An alternative is switched, never left with none.
        self.choose(option_two)
        self.assertEqual(self.choose(option_two, chosen=False), {"error": "refused"})
        self.assertTrue(option_two.twp_option_chosen)
        # Once confirmed, the choices are settled.
        self.order.action_confirm()
        self.assertEqual(self.choose(self.section(self.order, "HVLS fan")), {"error": "refused"})
        self.assertFalse(self.section(self.order, "HVLS fan").twp_option_chosen)
        self.assertNotIn("twp_option_choose", self.portal())

    def test_customer_and_salesperson_override_each_other(self):
        option_one, option_two = self.section(self.order, "Option 1"), self.section(self.order, "Option 2")
        option_one.twp_option_chosen = True
        self.choose(option_two)
        self.assertTrue(option_two.twp_option_chosen)
        self.assertFalse(option_one.twp_option_chosen)
        option_one.twp_option_chosen = True
        self.assertTrue(option_one.twp_option_chosen)
        self.assertFalse(option_two.twp_option_chosen)
        bodies = self.note_bodies(self.order)
        self.assertEqual(bodies.count("Chose Option 1"), 2)
        self.assertEqual(bodies.count("Chose Option 2"), 1)

    def test_emailed_choice_resent_then_changed_online_and_signed(self):
        option_one, option_two = self.section(self.order, "Option 1"), self.section(self.order, "Option 2")
        option_two.twp_option_chosen = True
        self.order.action_quotation_send()
        self.order.action_quotation_sent()
        self.assertEqual(self.order.state, "sent")
        self.assertIn("Your choice", self.portal())
        self.choose(option_one)
        self.assertTrue(option_one.twp_option_chosen)
        response = self.url_open(
            f"/my/orders/{self.order.id}/accept",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {
                "access_token": self.order.access_token, "name": "TWP Test Customer", "signature": SIGNATURE,
            }}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("error", response.json().get("result", {}))
        self.assertEqual(self.order.state, "sale")
        self.assertEqual(self.line(self.order, self.option_one).product_uom_qty, 2.0)
        self.assertEqual(self.line(self.order, self.option_two).product_uom_qty, 0.0)
        self.assertEqual(self.order.amount_untaxed, 6500.0)

    def test_choosing_settles_the_totals_block(self):
        page = self.portal()
        for name in ("Total with Option 1", "Total with Option 2", "Total with HVLS fan"):
            self.assertIn(name, page)
        self.choose(self.section(self.order, "Option 2"))
        page = self.portal()
        self.assertNotIn("Total with Option 1", page)
        self.assertNotIn("Total with Option 2", page)
        self.assertIn("Total with HVLS fan", page)
        pdf = self.env["ir.actions.report"]._render_qweb_html("sale.action_report_saleorder", self.order.ids)[0]
        self.assertNotIn(b"Total with Option 1", pdf)
        self.assertIn(b"Total with HVLS fan", pdf)
        self.choose(self.section(self.order, "HVLS fan"))
        page = self.portal()
        self.assertNotIn("Total with", page)
        self.assertNotIn("twp_option_totals", page)

    def test_each_set_settles_on_its_own(self):
        option_one, option_two = self.section(self.order, "Option 1"), self.section(self.order, "Option 2")
        option_two.twp_option_group = "Controls"
        self.choose(option_one)
        rows = [row["name"] for row in self.order._twp_option_totals()]
        self.assertEqual(rows, ["Option 2", "HVLS fan"], "Option 2 is a set of its own, still open")

    def test_pdf_has_no_controls(self):
        html = self.env["ir.actions.report"]._render_qweb_html("sale.action_report_saleorder", self.order.ids)[0]
        self.assertNotIn(b"twp_option_choose", html)
        self.assertIn(b"Not included in the total", html)
