from odoo.tests import HttpCase, TransactionCase, tagged

from .common import QuoteCase


@tagged("post_install", "-at_install")
class TestExclusion(QuoteCase, TransactionCase):
    """M0 proof 2: a line left out by _get_priced_lines stays out of every total."""

    def test_order_amounts(self):
        order = self.make_order()
        self.assertEqual(order.amount_untaxed, 6300.0)
        self.assertEqual(order.amount_tax, 630.0)
        self.assertEqual(order.amount_total, 6930.0)
        self.assertEqual(order.tax_totals["base_amount_currency"], 6300.0)
        self.assertEqual(order.tax_totals["total_amount_currency"], 6930.0)

    def test_alternatives_still_carry_their_price(self):
        order = self.make_order()
        self.assertEqual(self.line(order, self.option_one).price_subtotal, 200.0)
        self.assertEqual(self.line(order, self.fan).price_subtotal, 500.0)

    def test_choosing_moves_the_total(self):
        order = self.make_order()
        self.section(order, "Option 1").twp_option_chosen = True
        self.assertEqual(order.amount_untaxed, 6500.0)
        self.section(order, "HVLS fan").twp_option_chosen = True
        self.assertEqual(order.amount_untaxed, 7000.0)
        self.section(order, "HVLS fan").twp_option_mode = "included"
        self.assertEqual(order.amount_untaxed, 7000.0)

    def test_moving_a_line_into_an_alternative(self):
        order = self.make_order()
        self.line(order, self.bracket).sequence = 22
        # 15 brackets (300.00) now sit under Option 1, which is not chosen.
        self.assertEqual(order.amount_untaxed, 6000.0)

    def test_global_discount(self):
        order = self.make_order()
        self.env["sale.order.discount"].create({
            "sale_order_id": order.id,
            "discount_type": "so_discount",
            "discount_percentage": 0.1,
        }).action_apply_discount()
        discount = order.order_line.filtered(
            lambda l: l.product_id == self.env.company.sale_discount_product_id
        )
        self.assertEqual(sum(discount.mapped("price_subtotal")), -630.0)
        self.assertEqual(order.amount_untaxed, 5670.0)

    def test_fixed_discount(self):
        order = self.make_order()
        self.env["sale.order.discount"].create({
            "sale_order_id": order.id,
            "discount_type": "amount",
            "discount_amount": 630.0,
        }).action_apply_discount()
        # A fixed discount is an amount off the taxed total.
        self.assertEqual(order.amount_total, 6300.0)

    def test_line_discount_and_the_portal_saving(self):
        order = self.make_order()
        self.env["sale.order.discount"].create({
            "sale_order_id": order.id,
            "discount_type": "sol_discount",
            "discount_percentage": 0.1,
        }).action_apply_discount()
        self.assertEqual(order.amount_untaxed, 5670.0)
        self.assertEqual(order.amount_undiscounted, 6300.0)

    def test_down_payment(self):
        order = self.make_order()
        order.action_confirm()
        wizard = self.env["sale.advance.payment.inv"].with_context(
            active_model="sale.order", active_ids=order.ids, active_id=order.id,
        ).create({"advance_payment_method": "percentage", "amount": 50})
        wizard.create_invoices()
        invoice = order.invoice_ids
        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.amount_untaxed, 3150.0)
        self.assertEqual(invoice.amount_total, 3465.0)


@tagged("post_install", "-at_install")
class TestExclusionPortal(QuoteCase, HttpCase):
    """M0 proof 2, the portal half: the customer's page shows the included total."""

    def test_portal_total(self):
        order = self.make_order()
        order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("6,930.00", response.text)
        # What the total would be with every option counted.
        self.assertNotIn("8,030.00", response.text)
