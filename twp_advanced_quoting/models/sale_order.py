from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import is_html_empty

from .header_fields import apply_header_field_settings, header_field_cache_key, header_field_settings

# A price quoted on an option survives its quantity going to 0, and back.
PRICE_FIELDS = ("price_unit", "technical_price_unit", "discount")

# Changing any of these can move a line in or out of the order total.
EXCLUSION_DEPENDS = (
    "order_line.twp_option_mode",
    "order_line.twp_option_chosen",
    "order_line.sequence",
    "order_line.display_type",
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    twp_document_style_id = fields.Many2one(
        "twp.document.style",
        string="Document Style",
        compute="_compute_twp_document_style_id",
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        check_company=True,
        help="How the quote is built and printed, set by the customer's tags.",
    )
    twp_structure = fields.Selection(related="twp_document_style_id.structure", string="Structure")
    twp_can_change_style = fields.Boolean(compute="_compute_twp_can_change_style")
    twp_allow_options = fields.Boolean(
        string="Allow Alternatives",
        copy=False,
        help="Let this itemized quote carry alternatives and add-ons. Every line in them still "
             "prints with its own price.",
    )
    twp_is_estimate = fields.Boolean(
        string="Budget Estimate",
        tracking=True,
        help="Printed as an estimate, with the estimate note from Settings. The customer can't "
             "accept it online.",
    )
    twp_style_issues = fields.Text(
        string="Style Issues",
        compute="_compute_twp_style_issues",
        help="What keeps an itemized quote from being printed, sent or confirmed.",
    )

    # Numbers. With separate order numbers on, `name` is the quote number until the order is
    # confirmed, then the order number; both are kept.
    twp_quote_number = fields.Char(string="Quote Number", copy=False, readonly=True, index="btree_not_null")
    twp_order_number = fields.Char(string="Order Number", copy=False, readonly=True, index="btree_not_null")

    # Header fields. Each company turns them on or off and renames them in Settings.
    twp_job_name = fields.Char(string="Job Name", help="Copied when the quote is duplicated, and carried to the invoice.")
    twp_ship_via = fields.Char(string="Ship Via", help="How the goods ship, such as Best Way.")
    twp_fob = fields.Char(string="FOB", help="Where ownership passes to the customer, such as Origin or Destination.")
    twp_freight = fields.Char(string="Freight", help="Such as Included, Prepaid & Add, or Allowed.")
    twp_lead_time = fields.Char(string="Estimated Lead Time", help="Such as 2-3 weeks.")
    twp_introduction = fields.Html(
        string="Introduction",
        compute="_compute_twp_introduction",
        store=True,
        readonly=False,
        precompute=True,
        help="Printed above the lines.",
    )

    twp_section_margins = fields.Html(
        string="Margins by Section",
        compute="_compute_twp_section_margins",
        sanitize=False,
        help="The amount, cost and margin of each section, bundle and option, from the lines' own margins.",
    )

    # ------------------------------------------------------------
    # Document styles
    # ------------------------------------------------------------

    @api.depends("partner_id", "sale_order_template_id", "company_id")
    def _compute_twp_document_style_id(self):
        for order in self:
            # A confirmed order keeps the style it was quoted in.
            if order.state not in ("draft", "sent") and order.twp_document_style_id:
                continue
            order.twp_document_style_id = order._twp_matched_style() or order.twp_document_style_id

    def _twp_matched_style(self):
        """The style the customer's tags give, else the template's, else the company default."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return (
            self.env["twp.document.style"]._twp_match(self.partner_id, company)
            or self.sale_order_template_id.twp_document_style_id
            or company.twp_default_document_style_id
        )

    @api.depends_context("uid")
    @api.depends("company_id")
    def _compute_twp_can_change_style(self):
        manager = self.env.user.has_group("sales_team.group_sale_manager")
        for order in self:
            order.twp_can_change_style = manager or (order.company_id or self.env.company).twp_reps_change_style

    def _twp_check_style_rights(self, vals):
        """A salesperson keeps the style the customer's tags give, and asks before allowing alternatives."""
        if self.env.su or self.env.user.has_group("sales_team.group_sale_manager"):
            return
        for order in self:
            if (
                "twp_document_style_id" in vals
                and not order.twp_can_change_style
                and order.twp_document_style_id != order._twp_matched_style()
            ):
                raise UserError(_(
                    "Only a Sales administrator can change the document style of %(order)s. "
                    "Its customer's tags give it %(style)s.",
                    order=order.name,
                    style=order._twp_matched_style().display_name or _("no style"),
                ))
            if vals.get("twp_allow_options") and order.company_id.twp_allow_options_by == "managers":
                raise UserError(_("Only a Sales administrator can allow alternatives on an itemized quote."))

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order, vals in zip(orders, vals_list):
            order._twp_check_style_rights(vals)
            if vals.get("twp_allow_options"):
                order._twp_log_allow_options()
        return orders

    def write(self, vals):
        allowing = self.filtered(lambda order: not order.twp_allow_options) if vals.get("twp_allow_options") else self.browse()
        result = super().write(vals)
        if "twp_document_style_id" in vals or vals.get("twp_allow_options"):
            self._twp_check_style_rights(vals)
        allowing._twp_log_allow_options()
        return result

    def _twp_log_allow_options(self):
        """Each use of the override is in the chatter (D7)."""
        for order in self:
            order.message_post(body=_(
                "Alternatives and add-ons allowed on this itemized quote. Every line in them still prints with its price."
            ))

    @api.depends(
        "twp_document_style_id.structure",
        "twp_allow_options",
        "order_line.display_type",
        "order_line.twp_is_bundle",
        "order_line.twp_option_mode",
        "order_line.twp_hide_on_documents",
        "order_line.twp_hide_price",
        "order_line.collapse_prices",
        "order_line.collapse_composition",
        "order_line.name",
    )
    def _compute_twp_style_issues(self):
        for order in self:
            issues = order._twp_style_issues()
            order.twp_style_issues = "\n".join(f"- {issue}" for issue in issues) if issues else False

    def _twp_style_issues(self):
        """What an itemized quote holds that its style does not allow, one sentence each."""
        self.ensure_one()
        if self.twp_document_style_id.structure != "itemized":
            return []
        issues = []
        for line in self.order_line.sorted("sequence"):
            name = (line.name or "").splitlines()[0] if line.name else line.product_id.display_name
            if line.display_type in ("line_section", "line_subsection"):
                if line.twp_is_bundle:
                    issues.append(_("%s is a bundle.", name))
                elif line.collapse_composition:
                    issues.append(_("%s hides its lines.", name))
                elif line.collapse_prices:
                    issues.append(_("%s hides its prices.", name))
                if line.twp_option_mode != "included" and not self.twp_allow_options:
                    if line.twp_option_mode == "alternative":
                        issues.append(_("%s is an alternative.", name))
                    else:
                        issues.append(_("%s is an add-on.", name))
            elif not line.display_type and not line._twp_is_special():
                if line.twp_hide_on_documents:
                    issues.append(_("%s is hidden on documents.", name))
                elif line.twp_hide_price:
                    issues.append(_("%s hides its price.", name))
        return issues

    def _twp_style_error_message(self):
        """Why an itemized quote can't be printed, sent or confirmed yet, or an empty string."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            return ""
        issues = self._twp_style_issues()
        if not issues:
            return ""
        message = _(
            "%(order)s is in the %(style)s style, which prints every line with its own price. "
            "Before it can be printed, sent or confirmed:\n%(issues)s",
            order=self.name,
            style=self.twp_document_style_id.display_name,
            issues="\n".join(f"- {issue}" for issue in issues),
        )
        return message

    def _twp_check_style(self):
        for order in self:
            message = order._twp_style_error_message()
            if message:
                raise UserError(message)

    def _confirmation_error_message(self):
        return super()._confirmation_error_message() or self._twp_style_error_message()

    def action_quotation_send(self):
        self._twp_check_style()
        return super().action_quotation_send()

    def _twp_title(self):
        """The title the style gives this quote or order, or False for Odoo's own."""
        self.ensure_one()
        if self.state in ("draft", "sent", "cancel"):
            if self.twp_is_estimate:
                return self.company_id.twp_estimate_title or _("Estimate")
            return self.twp_document_style_id.title_word
        return self.twp_document_style_id.order_title_word

    @api.depends("twp_document_style_id", "twp_is_estimate")
    def _compute_type_name(self):
        super()._compute_type_name()
        for order in self:
            title = order._twp_title()
            if title:
                order.type_name = title

    def _get_report_base_filename(self):
        """Title, number and Job Name (D14), such as "Proposal - REDQ0001 - Main Street School"."""
        self.ensure_one()
        return " - ".join(part for part in (self.type_name, self.name, self.twp_job_name) if part)

    def _twp_show_estimate_note(self):
        self.ensure_one()
        return (
            self.twp_is_estimate
            and self.state in ("draft", "sent")
            and not is_html_empty(self.company_id.twp_estimate_note)
        )

    def _twp_net_prices(self):
        """Unit prices print with their discount taken off, and no discount column (D9)."""
        self.ensure_one()
        return self.twp_document_style_id.discount_column == "net"

    def _twp_show_taxes(self):
        self.ensure_one()
        return not self.twp_document_style_id or self.twp_document_style_id.show_taxes

    @api.depends("sale_order_template_id")
    def _compute_twp_introduction(self):
        for order in self:
            if not order.company_id.twp_introduction_enabled:
                order.twp_introduction = order.twp_introduction
                continue
            template = order.sale_order_template_id.with_context(lang=order.partner_id.lang)
            if template and not is_html_empty(template.twp_introduction):
                order.twp_introduction = template.twp_introduction
            elif is_html_empty(order.twp_introduction):
                company = order.company_id.with_context(lang=order.partner_id.lang)
                order.twp_introduction = company.twp_introduction_default

    @api.depends(
        "order_line.margin",
        "order_line.price_subtotal",
        "order_line.sequence",
        "order_line.display_type",
        "order_line.name",
        "order_line.twp_is_bundle",
        "order_line.twp_bundle_qty",
    )
    def _compute_twp_section_margins(self):
        for order in self:
            rows = order._twp_section_margin_rows()
            order.twp_section_margins = self.env["ir.qweb"]._render(
                "twp_advanced_quoting.section_margins",
                {"order": order, "rows": rows, "show_bundle_qty": any(row["bundle_qty"] for row in rows)},
            ) if rows else False

    def _twp_section_margin_rows(self):
        """[{name, subsection, bundle_qty, amount, cost, margin, margin_percent}] per section."""
        self.ensure_one()
        self.order_line._twp_refresh_parents()
        rows = []
        for section in self.order_line.filtered(
            lambda line: line.display_type in ("line_section", "line_subsection") and not line.is_downpayment
        ):
            lines = section._get_section_lines().filtered(lambda line: not line._twp_is_special())
            if not lines:
                continue
            amount = sum(lines.mapped("price_subtotal"))
            margin = sum(lines.mapped("margin"))
            rows.append({
                "name": section.name,
                "subsection": section.display_type == "line_subsection",
                "bundle_qty": section.twp_bundle_qty if section.twp_is_bundle else False,
                "amount": amount,
                "cost": amount - margin,
                "margin": margin,
                "margin_percent": margin / amount if amount else False,
            })
        return rows

    @api.onchange("order_line")
    def _twp_onchange_bundles(self):
        # The editor shows a member's quantity follow its bundle before the quote is saved.
        self.order_line._twp_sync_bundles()

    @property
    def _rec_names_search(self):
        return [*super()._rec_names_search, "twp_quote_number", "twp_order_number"]

    # ------------------------------------------------------------
    # Order numbers
    # ------------------------------------------------------------

    def action_confirm(self):
        # Checked here as well as in super, so a refused confirmation spends no order number.
        for order in self:
            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)
        # The Confirm button asks what the customer chose; any other confirmation, such as the
        # customer signing online, takes the options as they are marked.
        if (
            self.env.context.get("twp_ask_options")
            and len(self) == 1
            and self.company_id.twp_ask_options_on_confirm
            and self._twp_options()
        ):
            return self._twp_action_choose_options()
        self._twp_settle_options()
        # Numbered before super, so deliveries, purchases and the confirmation email carry it.
        self.filtered(lambda order: order.company_id.twp_number_orders)._twp_take_order_number()
        return super().action_confirm()

    def _twp_take_order_number(self):
        for order in self:
            quote_number = order.twp_quote_number or order.name
            order_number = order.twp_order_number or self.env["ir.sequence"].with_company(
                order.company_id
            ).next_by_code("twp.sale.order.confirmed", sequence_date=fields.Date.context_today(order))
            if not order_number:
                continue
            order.write({
                "twp_quote_number": quote_number,
                "twp_order_number": order_number,
                "name": order_number,
            })
            order.message_post(body=_("Quote %(quote)s confirmed as order %(order)s.", quote=quote_number, order=order_number))

    def action_draft(self):
        # Back to a quote: it reads as the quote it was. Confirming again reuses its order number.
        orders = self.filtered(lambda order: order.state in ("cancel", "sent"))
        result = super().action_draft()
        for order in orders.filtered(lambda o: o.twp_quote_number and o.name == o.twp_order_number):
            order.name = order.twp_quote_number
        orders.filtered(lambda order: order.state == "draft")._twp_restore_options()
        return result

    # ------------------------------------------------------------
    # Alternatives and add-ons
    # ------------------------------------------------------------

    def _twp_options(self):
        """The alternatives and add-ons on these orders that carry products, in order."""
        self.order_line._twp_refresh_parents()
        return self.order_line.sorted("sequence").filtered(
            lambda line: line._twp_is_option()
            and any(not member.display_type for member in line._twp_section_members())
        )

    def _twp_action_choose_options(self):
        self.ensure_one()
        wizard = self.env["twp.option.choice"].create({
            "order_id": self.id,
            "line_ids": [
                Command.create({"section_id": section.id, "chosen": section.twp_option_chosen})
                for section in self._twp_options()
            ],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("What did the customer choose?"),
            "res_model": "twp.option.choice",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _twp_settle_options(self):
        """Drop every option not chosen to quantity 0, kept on the order as a record (D3).

        Confirmed as they are, its lines would be delivered and invoiced.
        """
        for order in self:
            for section in order._twp_options().filtered(lambda s: not s.twp_option_chosen):
                members = (section | section._twp_section_members()).filtered(lambda line: not line.twp_not_chosen)
                products = members.filtered(lambda line: not line.display_type)
                with self.env.protecting([self.env["sale.order.line"]._fields[name] for name in PRICE_FIELDS], products):
                    for line in products:
                        line.write({
                            "twp_not_chosen": True,
                            "twp_quoted_qty": line.product_uom_qty,
                            "product_uom_qty": 0.0,
                        })
                (members - products).write({"twp_not_chosen": True})
            if order.order_line.filtered("twp_not_chosen"):
                order.message_post(body=_(
                    "Confirmed without: %s.",
                    ", ".join(order.order_line.filtered(lambda l: l.twp_not_chosen and l._twp_is_option()).mapped("name")),
                ))

    def _twp_restore_options(self):
        """Back to a quote, every option not chosen is quoted again at its quantities."""
        for order in self:
            lines = order.order_line.filtered("twp_not_chosen")
            products = lines.filtered(lambda line: not line.display_type)
            with self.env.protecting([self.env["sale.order.line"]._fields[name] for name in PRICE_FIELDS], products):
                for line in products:
                    line.write({"twp_not_chosen": False, "product_uom_qty": line.twp_quoted_qty})
            (lines - products).write({"twp_not_chosen": False})

    def _twp_options_only(self):
        """A quote whose every product is in an alternative or add-on not chosen (D2)."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            return False
        self.order_line._twp_refresh_parents()
        lines = self.order_line.filtered(lambda line: not line.display_type and not line._twp_is_special())
        return bool(lines) and all(line._twp_is_excluded() for line in lines)

    def _twp_needs_choice(self):
        """A quote the customer can't accept online yet: a set of alternatives with none chosen,
        or nothing but options."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            return False
        alternatives = self._twp_options().filtered(lambda line: line.twp_option_mode == "alternative")
        return self._twp_options_only() or any(
            not section._twp_alternatives().filtered("twp_option_chosen") for section in alternatives
        )

    def _twp_show_totals(self):
        self.ensure_one()
        return self.twp_document_style_id.totals_mode != "hidden" and not self._twp_options_only()

    def _twp_amount_total(self, lines):
        AccountTax = self.env["account.tax"]
        base_lines = [line._prepare_base_line_for_taxes_computation() for line in lines]
        AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return AccountTax._get_tax_totals_summary(
            base_lines=base_lines,
            currency=self.currency_id or self.company_id.currency_id,
            company=self.company_id,
        )["total_amount_currency"]

    def _twp_option_totals(self):
        """[{name, amount}]: the order's total with each option not chosen, for the totals block.

        An alternative takes the place of the one chosen in its set, if any.
        """
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            return []
        options = self._twp_options()
        lines = self.order_line.filtered(lambda line: not line.display_type)
        included = lines.filtered(lambda line: not line._twp_is_excluded())
        rows = []
        for section in options.filtered(lambda s: not s.twp_option_chosen):
            members = section._twp_section_members().filtered(lambda line: not line.display_type)
            with_option = included
            if section.twp_option_mode == "alternative":
                for chosen in section._twp_alternatives().filtered("twp_option_chosen"):
                    with_option -= chosen._twp_section_members()
            # A line inside another option not chosen stays out.
            with_option |= members.filtered(lambda line: all(
                other == section or other.twp_option_mode == "included" or other.twp_option_chosen
                for other in line._twp_enclosing_sections()
            ))
            rows.append({
                "name": (section.name or "").splitlines()[0] if section.name else "",
                "amount": self._twp_amount_total(with_option),
            })
        return rows

    def _twp_can_accept_online(self):
        """A choice still open, an estimate, or an itemized quote that isn't yet: no online accept."""
        self.ensure_one()
        return not (self._twp_needs_choice() or self.twp_is_estimate or self._twp_style_error_message())

    def _has_to_be_signed(self):
        return super()._has_to_be_signed() and self._twp_can_accept_online()

    def _has_to_be_paid(self):
        return super()._has_to_be_paid() and self._twp_can_accept_online()

    # ------------------------------------------------------------
    # Header fields on the form and the documents
    # ------------------------------------------------------------

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + header_field_cache_key(self.env.company)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            arch = apply_header_field_settings(arch, self.env.company)
            if not self.env.company.twp_introduction_enabled:
                for node in arch.xpath("//page[@name='twp_introduction']"):
                    node.set("invisible", "1")
        return arch, view

    def _twp_header_fields(self):
        """[{name, label, value}] for each header field that is turned on and filled in."""
        self.ensure_one()
        style = self.twp_document_style_id
        return [
            {"name": name, "label": label, "value": self[name]}
            for name, label, enabled in header_field_settings(self.company_id)
            if enabled and self[name] and style._twp_prints(name.removeprefix("twp_"))
        ]

    def _twp_show_introduction(self):
        self.ensure_one()
        return (
            self.company_id.twp_introduction_enabled
            and self.twp_document_style_id._twp_prints("introduction")
            and not is_html_empty(self.twp_introduction)
        )

    def _twp_line_numbers(self, lines):
        """{line id: number} for the numbered rows among the lines to print.

        A bundle takes one number on its own row and its members print without one; every
        other product row is numbered.
        """
        numbered = lines.filtered(
            lambda line: line.twp_is_bundle if line.display_type
            else line.product_type != "combo" and not line._twp_bundle()
        )
        return {line.id: number for number, line in enumerate(numbered, start=1)}

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values["twp_job_name"] = self.twp_job_name
        return values

    def _get_priced_lines(self):
        lines = super()._get_priced_lines()
        lines._twp_refresh_parents()
        return lines.filtered(lambda line: not line._twp_is_excluded())

    @api.depends(*EXCLUSION_DEPENDS)
    def _compute_amounts(self):
        return super()._compute_amounts()

    @api.depends(*EXCLUSION_DEPENDS)
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.depends(*EXCLUSION_DEPENDS)
    def _compute_amount_undiscounted(self):
        # Odoo sums every line here itself, and the portal shows the difference from the
        # untaxed amount as the customer's saving, so excluded lines come off.
        super()._compute_amount_undiscounted()
        AccountTax = self.env["account.tax"]
        self.order_line._twp_refresh_parents()
        for order in self:
            for line in order.order_line.filtered(lambda l: l._twp_is_excluded()):
                base_line = line._prepare_base_line_for_taxes_computation(discount=0)
                if not base_line.get("special_type"):
                    AccountTax._add_tax_details_in_base_line(base_line, order.company_id)
                    order.amount_undiscounted -= base_line["tax_details"]["raw_total_excluded_currency"]

    def _get_order_lines_to_report(self):
        return super()._get_order_lines_to_report().filtered(
            lambda line: not line.twp_hide_on_documents and not line.twp_not_chosen
        )
