{
    "name": "Advanced Quoting",
    "summary": "Bundles, alternatives kept out of the total, and quote styles set by the customer's tag",
    "version": "19.0.0.1.0",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "author": "ThriveWell Partners",
    "depends": ["sale_management", "sale_margin"],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
        "report/sale_report_templates.xml",
        "report/invoice_report_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "twp_advanced_quoting/static/src/**/*",
        ],
    },
    "installable": True,
}
