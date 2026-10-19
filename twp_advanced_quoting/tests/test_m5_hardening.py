from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_m3_options import OptionCase


@tagged("post_install", "-at_install")
class TestOptionalSections(OptionCase, TransactionCase):
    """Odoo's optional section offers its lines online at quantity 0, so it is neither a bundle
    nor an alternative or add-on."""

    def optional_section(self, order):
        section = self.section(order, "HVLS fan")
        section.twp_option_mode = "included"
        section.is_optional = True
        return section

    def test_optional_section_cannot_become_a_bundle(self):
        section = self.optional_section(self.make_order())
        with self.assertRaises(ValidationError):
            section.twp_is_bundle = True

    def test_optional_section_cannot_become_an_option(self):
        section = self.optional_section(self.make_order())
        for mode in ("alternative", "addon"):
            with self.assertRaises(ValidationError):
                section.twp_option_mode = mode

    def test_bundle_cannot_become_optional(self):
        order = self.make_order()
        with self.assertRaises(ValidationError):
            self.section(order, "Heater package").is_optional = True
        with self.assertRaises(ValidationError):
            self.section(order, "Option 1").is_optional = True

    def test_subsection_of_an_optional_section(self):
        order = self.make_order()
        section = self.optional_section(order)
        order.write({"order_line": [
            Command.create({"display_type": "line_subsection", "name": "Fan kit", "sequence": 42}),
        ]})
        subsection = self.section(order, "Fan kit")
        with self.assertRaises(ValidationError):
            subsection.twp_is_bundle = True
        # Unset Optional, and it can be.
        section.is_optional = False
        subsection.twp_is_bundle = True
        self.assertTrue(subsection.twp_is_bundle)

    def test_template_bundle_cannot_be_optional(self):
        template = self.env["sale.order.template"].create({
            "name": "TWP M5 Template",
            "sale_order_template_line_ids": [
                Command.create({"display_type": "line_section", "name": "Package", "twp_is_bundle": True}),
                Command.create({"product_id": self.heater.id, "product_uom_qty": 1}),
            ],
        })
        section = template.sale_order_template_line_ids.filtered("display_type")
        with self.assertRaises(ValidationError):
            section.is_optional = True


@tagged("post_install", "-at_install")
class TestSectionsFollowTheLines(OptionCase, TransactionCase):
    """Which section a line sits in is read once per order, and read again whenever the lines,
    their order or their kinds change in the same transaction."""

    def test_line_moved_out_of_an_option(self):
        order = self.make_order()
        self.assertEqual(order.amount_untaxed, 6300.0)
        fan = self.line(order, self.fan)
        # Into the heater package, where it is one per bundle: 5 fans.
        fan.sequence = 15
        self.assertEqual(order.amount_untaxed, 6300.0 + 2500.0)
        self.assertTrue(fan.twp_in_bundle)
        fan.sequence = 41
        self.assertEqual(order.amount_untaxed, 6300.0)
        self.assertFalse(fan.twp_in_bundle)

    def test_section_removed(self):
        order = self.make_order()
        self.section(order, "HVLS fan").unlink()
        # The fan now sits under Option 2, still out of the total.
        self.assertEqual(order.amount_untaxed, 6300.0)
        self.section(order, "Option 2").twp_option_chosen = True
        self.assertEqual(order.amount_untaxed, 6300.0 + 300.0 + 500.0)

    def test_many_sections(self):
        """Twenty sections, each kind in turn, total what their included lines do."""
        lines = []
        expected = 0.0
        for number in range(20):
            kind = number % 4
            lines.append(Command.create({
                "display_type": "line_section",
                "name": f"Section {number}",
                "sequence": number * 100,
                "twp_is_bundle": kind == 0,
                "twp_bundle_qty": 2 if kind == 0 else 1,
                "twp_option_mode": {1: "alternative", 2: "addon"}.get(kind, "included"),
                "twp_option_group": f"Set {number}" if kind == 1 else False,
            }))
            for position in range(1, 6):
                lines.append(Command.create({
                    "product_id": self.option_one.id,
                    "product_uom_qty": 1,
                    "sequence": number * 100 + position,
                }))
            if kind == 0:
                expected += 5 * 2 * 100.0
            elif kind == 3:
                expected += 5 * 100.0
        order = self.env["sale.order"].create({"partner_id": self.partner.id, "order_line": lines})
        self.assertEqual(order.amount_untaxed, expected)
        self.assertEqual(len(order._twp_options()), 10)


@tagged("post_install", "-at_install")
class TestSalesperson(OptionCase, TransactionCase):
    """A salesperson with no other rights builds, prints and confirms a quote with everything in it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rep = new_test_user(cls.env, login="twp_m5_rep", groups="sales_team.group_sale_salesman")

    def test_build_print_and_confirm(self):
        order = self.make_order()
        order.user_id = self.rep
        order = order.with_user(self.rep)
        self.section(order, "Heater package").twp_bundle_qty = 2
        self.section(order, "HVLS fan").twp_option_chosen = True
        self.assertEqual(order.amount_untaxed, 2520.0 + 500.0)
        html, _type = self.env["ir.actions.report"].with_user(self.rep)._render_qweb_html(
            "sale.report_saleorder", order.ids
        )
        self.assertIn("Heater package", html.decode())
        self.assertIn("Heater package", order.twp_section_margins)
        action = self.confirm_from_button(order)
        wizard = self.env["twp.option.choice"].with_user(self.rep).browse(action["res_id"])
        wizard.line_ids.filtered(lambda l: l.name == "Option 2").chosen = True
        wizard.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.amount_untaxed, 2520.0 + 300.0 + 500.0)
