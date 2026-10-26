from . import models

# Odoo's own file name for the quote report, put back when the module is uninstalled.
SALE_REPORT_NAME = "(object.state in ('draft', 'sent') and 'Quotation - %s' % (object.name)) or 'Order - %s' % (object.name)"


def rebuild_company_styles(env):
    """Rebuild Odoo's company report stylesheet, which carries the options' colours.

    Odoo rebuilds it only when a company's Document Layout changes. While this module installs or
    upgrades, Odoo leaves its views out of what it renders unless it is named as the module being
    installed, and a template compiled earlier would be reused, so the cache is cleared first.
    """
    env.registry.clear_cache("templates")
    env["res.company"].with_context(install_module="twp_advanced_quoting")._update_asset_style()


def post_init_hook(env):
    """Point every company at the shipped Bundle Adjustment product and the Grouped style."""
    product = env.ref("twp_advanced_quoting.product_bundle_adjustment", raise_if_not_found=False)
    if product:
        env["res.company"].search([("twp_bundle_adjustment_product_id", "=", False)]).write(
            {"twp_bundle_adjustment_product_id": product.id}
        )
    style = env.ref("twp_advanced_quoting.document_style_grouped", raise_if_not_found=False)
    if style:
        env["res.company"].search([("twp_default_document_style_id", "=", False)]).write(
            {"twp_default_document_style_id": style.id}
        )
    rebuild_company_styles(env)


def uninstall_hook(env):
    # The company report stylesheet is rebuilt without the options' colours.
    styles = env.ref("twp_advanced_quoting.styles_company_report", raise_if_not_found=False)
    if styles:
        styles.active = False
        rebuild_company_styles(env)
    report = env.ref("sale.action_report_saleorder", raise_if_not_found=False)
    if report:
        report.print_report_name = SALE_REPORT_NAME
