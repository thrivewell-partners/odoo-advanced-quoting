{
    "name": "Bids",
    "summary": "Bids built like quotes, kept out of Quotations until one is won",
    "description": """
A bid is a quotation sent to one of several bidders on the same job, where only one will win. It is
built, printed and emailed like any quote, with everything Advanced Quoting adds, but it carries its
own number series (set in Settings beside quote and order numbers), lives under Sales > Bids, and
never shows in Quotations or on an opportunity's Quotations button.

Copy to Customers sends one bid to several bidders, each with its own number. Won turns the bid into
an ordinary quotation with the next quote number, and marks the other open bids on the same
opportunity lost; from there it follows the normal Sales process. A bid can't be confirmed or
accepted online until it is won.
""",
    "version": "19.0.0.1.0",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "author": "ThriveWell Partners",
    "depends": ["twp_advanced_quoting", "sale_crm"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/mail_template_data.xml",
        "views/sale_order_views.xml",
        "views/crm_lead_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/twp_bid_copy_views.xml",
        "report/sale_report_templates.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
}
