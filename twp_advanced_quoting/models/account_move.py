from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_move_lines_to_report(self):
        return super()._get_move_lines_to_report().filtered(
            lambda line: not line.twp_hide_on_documents
        )
