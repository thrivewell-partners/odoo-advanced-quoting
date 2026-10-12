from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQuoteNumbers(TransactionCase):
    """M1: the quote number prefix, digits and next number in Settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "TWP Numbers Customer"})

    def settings(self, **values):
        settings = self.env["res.config.settings"].create(values)
        settings.execute()
        return settings

    def test_settings_show_the_sequence(self):
        sequence = self.env["res.config.settings"]._twp_quote_sequence()
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.twp_quote_prefix, sequence.prefix)
        self.assertEqual(settings.twp_quote_padding, sequence.padding)
        self.assertEqual(settings.twp_quote_next_number, sequence.number_next_actual)

    def test_new_prefix(self):
        before = self.env["sale.order"].create({"partner_id": self.partner.id})
        old_name = before.name
        self.settings(twp_quote_prefix="REDQ", twp_quote_padding=4, twp_quote_next_number=1)
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(order.name, "REDQ0001")
        self.assertEqual(self.env["sale.order"].create({"partner_id": self.partner.id}).name, "REDQ0002")
        self.assertEqual(before.name, old_name)

    def test_carry_on_counting(self):
        # Radiant may carry on from QuoteWerks' last number, MJOQ6922.
        self.settings(twp_quote_prefix="REDQ", twp_quote_padding=4, twp_quote_next_number=6923)
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(order.name, "REDQ6923")

    def test_confirmed_order_keeps_its_number(self):
        self.settings(twp_quote_prefix="REDQ", twp_quote_padding=4, twp_quote_next_number=7)
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        order.action_confirm()
        self.assertEqual(order.name, "REDQ0007")

    def test_saving_other_settings_leaves_the_sequence(self):
        self.settings(twp_quote_prefix="REDQ", twp_quote_padding=4, twp_quote_next_number=50)
        self.assertEqual(self.env["sale.order"].create({"partner_id": self.partner.id}).name, "REDQ0050")
        # Settings opened and saved again: the counter has moved on and must not go back.
        self.env["res.config.settings"].create({}).execute()
        self.assertEqual(self.env["sale.order"].create({"partner_id": self.partner.id}).name, "REDQ0051")
