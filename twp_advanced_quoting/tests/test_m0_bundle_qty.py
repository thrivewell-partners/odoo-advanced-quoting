from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import QuoteCase


@tagged("post_install", "-at_install")
class TestBundleQuantities(QuoteCase, TransactionCase):
    """M0 proof 4: bundle quantities hold on the server, however the line is written."""

    def quantities(self, order):
        return [self.line(order, p).product_uom_qty for p in (self.heater, self.bracket, self.labor)]

    def test_create(self):
        order = self.make_order()
        self.assertEqual(self.quantities(order), [5.0, 15.0, 5.0])

    def test_bundle_is_hide_prices(self):
        section = self.section(self.make_order(), "Heater package")
        self.assertTrue(section.collapse_prices)
        self.assertFalse(section.collapse_composition)

    def test_write_on_the_section(self):
        order = self.make_order()
        self.section(order, "Heater package").write({"twp_bundle_qty": 6})
        self.assertEqual(self.quantities(order), [6.0, 18.0, 6.0])

    def test_write_through_the_order(self):
        # The form saves order lines as commands on the order.
        order = self.make_order()
        section = self.section(order, "Heater package")
        order.write({"order_line": [Command.update(section.id, {"twp_bundle_qty": 2})]})
        self.assertEqual(self.quantities(order), [2.0, 6.0, 2.0])

    def test_per_bundle_quantity(self):
        order = self.make_order()
        self.line(order, self.bracket).twp_qty_per_bundle = 4
        self.assertEqual(self.quantities(order), [5.0, 20.0, 5.0])

    def test_ordered_quantity_written_directly(self):
        # D15: inside a bundle only the quantity per bundle is typed, so this is put back.
        order = self.make_order()
        heater = self.line(order, self.heater)
        heater.product_uom_qty = 10
        self.assertEqual(heater.twp_qty_per_bundle, 1.0)
        self.assertEqual(heater.product_uom_qty, 5.0)
        self.section(order, "Heater package").twp_bundle_qty = 6
        self.assertEqual(heater.product_uom_qty, 6.0)

    def test_member_added_later(self):
        order = self.make_order(bundle_only=True)
        order.write({"order_line": [Command.create({
            "product_id": self.fan.id, "twp_qty_per_bundle": 2, "sequence": 14,
        })]})
        self.assertEqual(self.line(order, self.fan).product_uom_qty, 10.0)

    def test_line_moved_out_of_the_bundle(self):
        order = self.make_order()
        bracket = self.line(order, self.bracket)
        bracket.sequence = 22
        self.section(order, "Heater package").twp_bundle_qty = 6
        self.assertEqual(bracket.product_uom_qty, 15.0)
        self.assertEqual(self.line(order, self.heater).product_uom_qty, 6.0)

    def test_global_discount_is_not_a_member(self):
        # The wizard appends its line at sequence 999, under the last section: here, the bundle.
        order = self.make_order(bundle_only=True)
        self.env["sale.order.discount"].create({
            "sale_order_id": order.id,
            "discount_type": "so_discount",
            "discount_percentage": 0.1,
        }).action_apply_discount()
        discount = order.order_line.filtered(lambda l: l._is_global_discount())
        self.assertEqual(discount.product_uom_qty, 1.0)
        self.section(order, "Heater package").twp_bundle_qty = 6
        self.assertEqual(discount.product_uom_qty, 1.0)
        self.assertEqual(order.amount_untaxed, 7560.0 - 630.0)

    def test_confirmed_order(self):
        order = self.make_order(bundle_only=True)
        order.action_confirm()
        self.section(order, "Heater package").twp_bundle_qty = 7
        self.assertEqual(self.quantities(order), [7.0, 21.0, 7.0])


@tagged("post_install", "-at_install")
class TestBundleQuantitiesOverRpc(QuoteCase, HttpCase):
    """M0 proof 4 over the wire: a JSON-RPC write, as an integration would send it."""

    def test_rpc_write(self):
        order = self.make_order(bundle_only=True)
        section = self.section(order, "Heater package")
        self.authenticate("admin", "admin")
        self.make_jsonrpc_request("/web/dataset/call_kw/sale.order.line/write", {
            "model": "sale.order.line",
            "method": "write",
            "args": [section.ids, {"twp_bundle_qty": 3}],
            "kwargs": {},
        })
        order.invalidate_recordset()
        order.order_line.invalidate_recordset()
        self.assertEqual(
            [self.line(order, p).product_uom_qty for p in (self.heater, self.bracket, self.labor)],
            [3.0, 9.0, 3.0],
        )
