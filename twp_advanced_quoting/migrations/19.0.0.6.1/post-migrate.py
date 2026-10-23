from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Open quotes lose a sales description that only repeated the product's name.

    Only a line still worded as Odoo wrote it is changed, and only on a quote: a confirmed order
    keeps the words it was confirmed with.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["sale.order.line"].search([
        ("order_id.state", "in", ("draft", "sent")),
        ("display_type", "=", False),
        ("product_id.description_sale", "!=", False),
    ])
    for line in lines:
        product = line.product_id.with_context(lang=line.order_id._get_lang())
        if not product._twp_description_repeats_name():
            continue
        written = f"{product.display_name}\n{product.description_sale}"
        if line.name and line.name.startswith(written):
            line.name = product.display_name + line.name[len(written):]
