from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # An itemized quote that isn't itemized yet can't be printed, whichever way it is asked
        # for: the Print menu, the email, the customer's download or the PDF quote builder.
        report = self._get_report(report_ref)
        if report.model == "sale.order" and res_ids:
            ids = [res_ids] if isinstance(res_ids, int) else res_ids
            self.env["sale.order"].browse(ids)._twp_check_style()
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
