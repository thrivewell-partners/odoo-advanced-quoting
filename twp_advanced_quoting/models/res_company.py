from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    twp_job_name_enabled = fields.Boolean(string="Job Name", default=True)
    twp_job_name_label = fields.Char(string="Job Name Label", default="Job Name")
    twp_ship_via_enabled = fields.Boolean(string="Ship Via", default=True)
    twp_ship_via_label = fields.Char(string="Ship Via Label", default="Ship Via")
    twp_fob_enabled = fields.Boolean(string="FOB", default=True)
    twp_fob_label = fields.Char(string="FOB Label", default="FOB")
    twp_freight_enabled = fields.Boolean(string="Freight", default=True)
    twp_freight_label = fields.Char(string="Freight Label", default="Freight")
    twp_lead_time_enabled = fields.Boolean(string="Estimated Lead Time", default=True)
    twp_lead_time_label = fields.Char(string="Estimated Lead Time Label", default="Estimated Lead Time")
    twp_introduction_enabled = fields.Boolean(string="Introduction", default=True)
    twp_introduction_default = fields.Html(
        string="Default Introduction",
        translate=True,
        help="Printed above the lines of a new quote, unless its quotation template has its own.",
    )
