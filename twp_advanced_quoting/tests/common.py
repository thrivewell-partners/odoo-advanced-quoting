from odoo import Command


class QuoteCase:
    """A quote shaped like Radiant's MJOQ6922: a heater package, two alternatives and an add-on.

    The package is 5 heaters at 1,000.00, 3 brackets at 20.00 per heater, and a 200.00 labor
    line per heater that never prints. Included untaxed: 5,000 + 300 + 1,000 = 6,300.00. The
    alternatives (2 x 100, 1 x 300) and the add-on (500) would bring it to 7,300.00.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tax = cls.env["account.tax"].create({
            "name": "TWP Sales 10%",
            "amount": 10,
            "amount_type": "percent",
            "type_tax_use": "sale",
        })
        cls.heater = cls._product("TWP Heater", 1000)
        cls.bracket = cls._product("TWP Bracket", 20)
        cls.labor = cls._product("TWP Labor", 200)
        cls.option_one = cls._product("TWP Option One", 100)
        cls.option_two = cls._product("TWP Option Two", 300)
        cls.fan = cls._product("TWP Fan", 500)
        cls.partner = cls.env["res.partner"].create({"name": "TWP Test Customer"})
        # The earlier milestones' quotes have no style unless a test gives them one (M4 sets a default).
        cls.env.company.twp_default_document_style_id = False

    @classmethod
    def _product(cls, name, price):
        return cls.env["product.product"].create({
            "name": name,
            "type": "consu",
            "list_price": price,
            "invoice_policy": "order",
            "taxes_id": [Command.set(cls.tax.ids)],
        })

    def make_order(self, bundle_only=False):
        lines = [
            Command.create({
                "display_type": "line_section",
                "name": "Heater package",
                "twp_is_bundle": True,
                "twp_bundle_qty": 5,
                "sequence": 10,
            }),
            Command.create({"product_id": self.heater.id, "twp_qty_per_bundle": 1, "sequence": 11}),
            Command.create({"product_id": self.bracket.id, "twp_qty_per_bundle": 3, "sequence": 12}),
            Command.create({
                "product_id": self.labor.id,
                "twp_qty_per_bundle": 1,
                "twp_hide_on_documents": True,
                "sequence": 13,
            }),
        ]
        if not bundle_only:
            lines += [
                Command.create({
                    "display_type": "line_section",
                    "name": "Option 1",
                    "twp_option_mode": "alternative",
                    "twp_option_group": "Heater",
                    "sequence": 20,
                }),
                Command.create({"product_id": self.option_one.id, "product_uom_qty": 2, "sequence": 21}),
                Command.create({
                    "display_type": "line_section",
                    "name": "Option 2",
                    "twp_option_mode": "alternative",
                    "twp_option_group": "Heater",
                    "sequence": 30,
                }),
                Command.create({"product_id": self.option_two.id, "product_uom_qty": 1, "sequence": 31}),
                Command.create({
                    "display_type": "line_section",
                    "name": "HVLS fan",
                    "twp_option_mode": "addon",
                    "sequence": 40,
                }),
                Command.create({"product_id": self.fan.id, "product_uom_qty": 1, "sequence": 41}),
            ]
        return self.env["sale.order"].create({"partner_id": self.partner.id, "order_line": lines})

    def line(self, order, product):
        return order.order_line.filtered(lambda l: l.product_id == product)

    def section(self, order, name):
        return order.order_line.filtered(lambda l: l.display_type and l.name == name)
