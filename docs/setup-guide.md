# Advanced Quoting in Odoo: setting it up

This guide is for the people at your business who set up Advanced Quoting and the people who
quote with it. ThriveWell does the setup with you, so most of it is ours to do. The parts that are
yours are marked.

## What it does

Advanced Quoting adds to Odoo's Sales app what a distributor's quote needs:

- **Bundles.** A priced package row, with the items in it listed underneath without prices. Each
  item has a quantity per package, and changing the number of packages moves every item with it.
- **Alternatives and add-ons.** "Option 1 or Option 2", and extras such as a fan, each printed with
  its own price and kept out of the quote's total until the customer chooses it. The total Odoo
  stores is what the customer is actually buying.
- **Document styles set by the customer.** A distributor gets a plain itemized quote; a contractor
  gets bundles and options. The style follows a tag on the customer, so nobody has to remember.
- **Quote fields** such as Job Name, Ship Via, FOB, Freight and Lead Time, an introduction above
  the lines, and your own quote, order and invoice numbers.
- **Budget estimates,** printed as an estimate with your wording.
- **Bids** (optional, the Bids module): quotes sent to several bidders on the same job, kept out of
  your Quotations until one is won.

It works inside Odoo's own quote, so the PDF, the email, the customer's online page and the
invoice all follow it.

## Questions we'll ask you (yours to answer)

**1. How should your numbers look?** Quotes, confirmed orders and invoices can each have their own
prefix, such as Q, O and I after your initials. Choose the prefix, how many digits, and the next
number, so the first Odoo quote carries on from your old system. Numbers already given never
change. If you take Bids, they get a series of their own.

**2. What kinds of customer do you have, and how should each be quoted?** Usually two kinds:
- **Itemized** for distributors and wholesalers: every line with its own price, no bundles, nothing
  hidden. An itemized quote with a bundle or a hidden line can be saved, but not printed, sent or
  confirmed until it is fixed. The quote says what to fix.
- **Grouped** for contractors and end customers: bundles, alternatives and add-ons allowed.

We make a tag for each kind (Distributor, Wholesaler, Contractor, or your own words), put it on
the style it belongs to, and put it on your customers. A customer with no tag gets the default
style you choose. Each style also sets the quote's title (such as Proposal), whether lines are
numbered, a Model No. column, and which quote fields print.

**3. Who may change things?** By default only a Sales administrator can change a quote's style
from what the customer's tag gives, or let an itemized quote carry alternatives. Either can be
opened to every salesperson. Each time alternatives are allowed on an itemized quote, the quote's
history records who did it.

**4. How should a bundle's items print?** Either the total quantity of each item, or the quantity
in one package, written "(3)" before the description.

**5. Which quote fields do you use, and what do you call them?** Each can be turned off or
renamed.

**6. What should an estimate say?** A title (Estimate) and a note printed above the lines (such as
"Budget pricing"). A customer can't accept an estimate online; to make it an offer, untick Budget
Estimate and send it as a quote.

## Prices: your pricelists (yours to decide, ours to set up)

Advanced Quoting adds no pricing rules of its own. Prices come from Odoo's pricelists, which
handle what most distributors do:

- **Each product's sales price is the manufacturer's list price.**
- **One product category per manufacturer or line,** so each can have its own discount.
- **A default pricelist** with one rule per category, such as list less 34% on one line and list
  less 18% on another.
- **A pricelist for each customer who buys differently,** such as list less 42%, set on that
  customer. Their quotes price themselves.
- **Net prices, no discount column.** Leave Odoo's Discounts setting off, so each rule's discount
  is taken off the unit price and the customer sees one net price. The styles also print net.
- **A one-off price** is typed on the line, and Odoo keeps it.
- **Cost** is each product's Cost field (list less your vendor discount), which gives the margin on
  each line, each bundle and each option on the quote's Margins tab.

Bring your price books as a spreadsheet and we load them, with each product's category and cost.

## What ThriveWell sets up

- Installs Advanced Quoting (and Bids, if you want it) and fills in **Settings**, under **Sales**,
  **Advanced Quoting**, from your answers.
- Makes your customer tags, puts them on the styles, and tags your customers.
- Loads your products, categories, costs and pricelists.
- Builds your first quotes with you, prints them, and checks them against what you send today.

## Day to day (each salesperson)

- **A bundle:** add a section, open its **⋮** menu and choose **Set Bundle**. Type the number of
  packages on the section row and each item's quantity per package. **Add Adjustment** adds a
  hidden line for markup or labor priced into the package.
- **Alternatives:** make a section for each choice and choose **Set Alternative**. Choices that
  belong together share an Option Group. An add-on is **Set Add-on**. When the customer decides,
  **Mark Chosen**, and the total follows. **Unset Alternative** or **Unset Add-on** makes it an
  ordinary section again, counted in the total. On the quote each option prints as its own
  shaded block with a tag, in the colour from **Settings > Document Layout** on the PDF and the
  website's theme colour online.
- **Lines on their own after a group:** open the group's **⋮** menu and choose **Add Standalone
  Lines**. A "Standalone items" divider appears after the group; the lines added below it belong
  to no bundle or option and print flush left at their own prices. The divider itself never
  prints. Deleting it deletes only the divider, and its lines join the group above.
- **Hiding one line:** the eye at the start of a line keeps it off the PDF, the online page and
  the invoice. It still counts in the price.
- **Confirming** a quote with options asks what the customer chose. What they didn't choose stays
  on the order at quantity 0, as a record, and is never delivered or invoiced.

Odoo's own **Set Optional** is not offered in the menu. It prints 0.00 until the customer adds the
lines online, which reads like an add-on but isn't priced; use **Set Add-on** instead.

## With Inventory

Nothing to set up. A confirmed order delivers what was chosen, at the true quantities, including
every item in a bundle. A line hidden on documents is still delivered and still on the delivery
slip, because it is in the box.

## If you stop using it (for your administrator)

Uninstalling removes everything Advanced Quoting added and puts Odoo's quote file name and menus
back. Your quotes, orders and invoices stay, with the numbers they were given, and new quotes keep
the prefix you chose until you change it in Odoo's sequences. Settle or remove any open
alternatives and add-ons first: once uninstalled they are ordinary lines, and the quote's total
counts them the next time it is edited.
