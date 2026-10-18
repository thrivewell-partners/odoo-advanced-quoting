# odoo-advanced-quoting

An Odoo 19 Community module for distribution quoting on top of the Sales app: bundles with
unpriced members, alternatives and add-ons kept out of the order total, distribution header fields,
and document styles set by the customer's tag. Configured by each client's admin in Settings. Radiant
Energy Distribution, moving off QuoteWerks, is the first client.

| Module | Status | What it does |
|---|---|---|
| `twp_advanced_quoting` | M4 done: document styles matched by the customer's tags, locked for salespeople; the itemized rule, with an Allow Alternatives override; title and order title, the file name (title, number, Job Name), net prices and the taxes column per style; the budget estimate switch; two shipped styles, Itemized and Grouped. Since M4 the editor marks a bundle or grouped section and its lines with a bar, and an eye on each line hides it on documents in one click. M3 before it: alternatives and add-ons kept out of the total until chosen, and the confirm dialog. M2: bundles. M1: header fields, introduction, Hide Price, line numbers and code column, quote, order and invoice numbers in Settings. Hardening (M5) next. Released to Radiant's staging on 2026-10-18, not yet to any production | Everything in the build map's s3.1 to s3.6 |
| `twp_bids` | Built 2026-10-18; on Radiant's staging with its bridge `radiant_bid_sale` | Bids built like quotes: their own number series in Settings beside quote numbers, Sales > Bids, kept out of Quotations and an opportunity's Quotations button, Copy to Customers, and Won (the bid becomes a quotation with the next quote number; the other open bids on the opportunity are marked lost) or Lost. A bid can't be confirmed or accepted online. Depends on `twp_advanced_quoting` and `sale_crm` |

This repo is the master copy. Releases are copied into each client's code repo, which is that
client's addons path on Oduflow.

The design lives in ThriveWell's tree at
`thrivewell/work/design/2026-10-12-advanced-quoting-build-map.md`, with what Odoo 19 already does in
`2026-10-12-advanced-quoting-odoo-base-map.md` beside it.
