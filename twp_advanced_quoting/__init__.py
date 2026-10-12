from . import models


def post_init_hook(env):
    """Point every company at the shipped Bundle Adjustment product."""
    product = env.ref("twp_advanced_quoting.product_bundle_adjustment", raise_if_not_found=False)
    if product:
        env["res.company"].search([("twp_bundle_adjustment_product_id", "=", False)]).write(
            {"twp_bundle_adjustment_product_id": product.id}
        )
