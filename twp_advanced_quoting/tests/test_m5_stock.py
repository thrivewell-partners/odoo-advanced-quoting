from odoo.tests import TransactionCase, tagged

from .test_m3_options import OptionCase


@tagged("post_install", "-at_install")
class TestDeliveries(OptionCase, TransactionCase):
    """With Inventory installed, a confirmed order delivers what was chosen, at its true
    quantities. Run only where `sale_stock` is installed; the module doesn't depend on it.
    """

    def setUp(self):
        super().setUp()
        if "picking_ids" not in self.env["sale.order"]._fields:
            self.skipTest("Inventory is not installed")

    def delivered(self, order):
        """{product: quantity} on the order's open deliveries."""
        moves = order.picking_ids.filtered(lambda p: p.state != "cancel").move_ids
        return {product: sum(moves.filtered(lambda m: m.product_id == product).mapped("product_uom_qty"))
                for product in moves.product_id}

    def test_only_what_was_chosen_is_delivered(self):
        order = self.make_order()
        self.section(order, "Option 1").twp_option_chosen = True
        order.action_confirm()
        self.assertEqual(self.delivered(order), {
            self.heater: 5.0,
            self.bracket: 15.0,
            # Hidden on documents, but goods all the same.
            self.labor: 5.0,
            self.option_one: 2.0,
        })

    def test_choice_changed_after_cancelling(self):
        order = self.make_order()
        self.section(order, "Option 1").twp_option_chosen = True
        order.action_confirm()
        order._action_cancel()
        order.action_draft()
        self.section(order, "Option 2").twp_option_chosen = True
        self.section(order, "HVLS fan").twp_option_chosen = True
        order.action_confirm()
        delivered = self.delivered(order)
        self.assertNotIn(self.option_one, delivered)
        self.assertEqual(delivered[self.option_two], 1.0)
        self.assertEqual(delivered[self.fan], 1.0)

    def test_more_packages_after_confirming(self):
        order = self.make_order(bundle_only=True)
        order.action_confirm()
        self.section(order, "Heater package").twp_bundle_qty = 6
        delivered = self.delivered(order)
        self.assertEqual(delivered[self.heater], 6.0)
        self.assertEqual(delivered[self.bracket], 18.0)

    def test_delivery_slip_prints(self):
        order = self.make_order()
        order.action_confirm()
        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "stock.report_deliveryslip", order.picking_ids.ids
        )
        self.assertIn(self.heater.name, html.decode())
        self.assertNotIn(self.fan.name, html.decode())
