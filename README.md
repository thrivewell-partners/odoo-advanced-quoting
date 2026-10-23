# odoo-advanced-quoting

An Odoo 19 Community module for distribution quoting on top of the Sales app: bundles with
unpriced members, alternatives and add-ons kept out of the order total, distribution header fields,
and document styles set by the customer's tag. Configured by each client's admin in Settings. Radiant
Energy Distribution, moving off QuoteWerks, is the first client.

| Module | Status | What it does |
|---|---|---|
| `twp_advanced_quoting` | M6 done 2026-10-23, 19.0.0.6.0: the product catalog. Its side panel lists subsections under their section, so Option 1, Option 2 or a bundle is added to directly; a line is matched to the innermost section or subsection around it, so the same product in two options is two lines; a bundle member reads and changes its quantity per bundle; a new line lands in its own group, above a section's subsections; dragging a section takes its subsections and their lines with it, and a subsection is not dragged. 151 tests in the sandbox. M5 before it, 2026-10-19: hardened. Odoo's Set Optional is offered only to undo it, a bundle's menu has no Show Prices, and an optional section is never a bundle or an option; each line reads its section from one pass over the order, so large quotes stay quick, with tests for a salesperson's quote and, where Inventory is installed, deliveries; uninstall checked to leave nothing of its own behind. M4 before it: document styles matched by the customer's tags, the itemized rule with an Allow Alternatives override, titles, file names, net prices and budget estimates. M3: alternatives and add-ons kept out of the total until chosen, and the confirm dialog. M2: bundles. M1: header fields, introduction, Hide Price, line numbers and code column, quote, order and invoice numbers. 19.0.0.6.1, 2026-10-23: with eCommerce installed the online quote printed each description twice, because eCommerce replaces Odoo's description with a product link that the code column's view could no longer hide (this was the staging failure in TestPortalDocument.test_portal); the description now has its own view that applies first. A sales description that only repeats the product's name, alone or after its reference, is left off new lines, and an upgrade takes it off open quotes' lines still worded as Odoo wrote them. Released to Radiant's staging at 19.0.0.6.1 on 2026-10-23, where every test passes, and not to any production | Everything in the build map's s3.1 to s3.6 |
| `twp_bids` | Built 2026-10-18; on Radiant's staging with its bridge `radiant_bid_sale` | Bids built like quotes: their own number series in Settings beside quote numbers, Sales > Bids, kept out of Quotations and an opportunity's Quotations button, Copy to Customers, and Won (the bid becomes a quotation with the next quote number; the other open bids on the opportunity are marked lost) or Lost. A bid can't be confirmed or accepted online. Depends on `twp_advanced_quoting` and `sale_crm` |

Setting it up with a client: [docs/setup-guide.md](docs/setup-guide.md), including the pricelist setup.

This repo is the master copy. Releases are copied into each client's code repo, which is that
client's addons path on Oduflow.

The design lives in ThriveWell's tree at
`thrivewell/work/design/2026-10-12-advanced-quoting-build-map.md`, with what Odoo 19 already does in
`2026-10-12-advanced-quoting-odoo-base-map.md` beside it.
