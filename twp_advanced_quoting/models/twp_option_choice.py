from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TwpOptionChoice(models.TransientModel):
    _name = "twp.option.choice"
    _description = "Options Chosen on Confirmation"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    line_ids = fields.One2many("twp.option.choice.line", "wizard_id", string="Options")

    def action_confirm(self):
        self.ensure_one()
        for line in self.line_ids.filtered(lambda l: l.chosen and l.option_mode == "alternative"):
            others = self.line_ids.filtered(
                lambda other: other != line
                and other.chosen
                and other.option_mode == "alternative"
                and (other.option_group or "") == (line.option_group or "")
            )
            if others:
                raise UserError(_(
                    "Choose one of %s: they are alternatives to each other.",
                    ", ".join((line | others).mapped("name")),
                ))
        # Unchosen first, so a newly chosen alternative never meets the old one.
        for line in self.line_ids.sorted("chosen"):
            if line.section_id.twp_option_chosen != line.chosen:
                line.section_id.twp_option_chosen = line.chosen
        return self.order_id.with_context(twp_ask_options=False, validate_analytic=True).action_confirm()


class TwpOptionChoiceLine(models.TransientModel):
    _name = "twp.option.choice.line"
    _description = "Option Chosen on Confirmation"
    _order = "sequence, id"

    wizard_id = fields.Many2one("twp.option.choice", required=True, ondelete="cascade")
    section_id = fields.Many2one("sale.order.line", required=True, ondelete="cascade")
    sequence = fields.Integer(related="section_id.sequence")
    name = fields.Text(related="section_id.name", string="Option")
    option_mode = fields.Selection(related="section_id.twp_option_mode", string="Kind")
    option_group = fields.Char(related="section_id.twp_option_group", string="Option Group")
    currency_id = fields.Many2one(related="section_id.currency_id")
    amount = fields.Monetary(string="Amount", compute="_compute_amount", currency_field="currency_id")
    chosen = fields.Boolean(string="Chosen")

    @api.depends("section_id")
    def _compute_amount(self):
        for line in self:
            members = line.section_id._twp_section_members().filtered(lambda member: not member.display_type)
            line.amount = sum(members.mapped("price_subtotal"))
