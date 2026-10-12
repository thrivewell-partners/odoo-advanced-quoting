# odoo-advanced-quoting

An Odoo 19 Community module for distribution quoting on top of the Sales app: bundles with
unpriced members, alternatives and add-ons kept out of the order total, distribution header fields,
and document styles set by the customer's tag. Configured by each client's admin in Settings. Radiant
Energy Distribution, moving off QuoteWerks, is the first client.

| Module | Status | What it does |
|---|---|---|
| `twp_advanced_quoting` | M3 done: alternatives and add-ons kept out of the total until chosen, one choice per set, a total with each option, no total on a quote of only options, and the confirm dialog that drops what wasn't chosen to quantity 0. M2 before it: bundles printed as one priced row, per-bundle quantities, bundles on quotation templates, the adjustment product, margins by section. M1: header fields, introduction, Hide Price, line numbers and code column, quote, order and invoice numbers in Settings. Document styles by customer tag (M4) next. Not yet released to any client | Everything in the build map's s3.1 to s3.6 |

This repo is the master copy. Releases are copied into each client's code repo, which is that
client's addons path on Oduflow.

The design lives in ThriveWell's tree at
`thrivewell/work/design/2026-10-12-advanced-quoting-build-map.md`, with what Odoo 19 already does in
`2026-10-12-advanced-quoting-odoo-base-map.md` beside it.
