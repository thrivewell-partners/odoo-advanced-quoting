from odoo import api, fields, models

from .header_fields import apply_header_field_settings, header_field_cache_key, header_field_settings

INVOICE_HEADER_FIELDS = ("job_name",)


class AccountMove(models.Model):
    _inherit = "account.move"

    twp_job_name = fields.Char(string="Job Name", help="Carried from the sales order.")

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + header_field_cache_key(self.env.company, INVOICE_HEADER_FIELDS)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            arch = apply_header_field_settings(arch, self.env.company, INVOICE_HEADER_FIELDS)
        return arch, view

    def _twp_header_fields(self):
        self.ensure_one()
        return [
            {"name": name, "label": label, "value": self[name]}
            for name, label, enabled in header_field_settings(self.company_id, INVOICE_HEADER_FIELDS)
            if enabled and self[name]
        ]

    def _get_move_lines_to_report(self):
        return super()._get_move_lines_to_report().filtered(
            lambda line: not line.twp_hide_on_documents
        )
