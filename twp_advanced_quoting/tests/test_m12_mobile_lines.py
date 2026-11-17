from odoo.tests import HttpCase, tagged

from .common import QuoteCase


@tagged("post_install", "-at_install")
class TestMobileLines(QuoteCase, HttpCase):
    """On a phone the quote lines are cards: the bundle and the options are drawn around them."""

    browser_size = "375x667"
    touch_enabled = True

    def test_phone_lines(self):
        order = self.make_order()
        bundle = order.order_line.filtered("twp_is_bundle")
        option_one = order.order_line.filtered(lambda line: line.name == "Option 1")
        labor = order.order_line.filtered(lambda line: line.product_id == self.labor)
        bracket = order.order_line.filtered(lambda line: line.product_id == self.bracket)
        action = self.env.ref("sale.action_quotations_with_onboarding")

        self.start_tour(f"/odoo/action-{action.id}/{order.id}", "twp_mobile_lines", login="admin")

        self.assertEqual(bundle.twp_bundle_qty, 6)
        self.assertEqual(bracket.product_uom_qty, 18)
        self.assertTrue(option_one.twp_option_chosen)
        self.assertFalse(labor.twp_hide_on_documents)
