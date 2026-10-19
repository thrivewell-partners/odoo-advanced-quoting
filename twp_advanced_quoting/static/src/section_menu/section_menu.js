import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { SaleOrderLineListRenderer } from "@sale/js/sale_order_line_field/sale_order_line_field";
import { SaleOrderTemplateLineListRenderer } from "@sale_management/fields/sale_order_template_line_field/sale_order_template_line_field";
import { useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

// Cells a bundle's or an option's row keeps beside its section total.
const TWP_SECTION_COLUMNS = ["twp_option_group", "twp_option_label", "twp_bundle_qty"];

/**
 * Whether a section prints its lines as one: a bundle, or Odoo's Hide Prices or Hide Composition.
 */
function twpGroups(record) {
    const data = record.data;
    return Boolean(data.twp_is_bundle || data.collapse_prices || data.collapse_composition);
}

patch(SectionAndNoteListRenderer.prototype, {
    setup() {
        super.setup();
        // The print toggle changes a line without opening it, so it asks the list.
        useSubEnv({
            twpCanChangeLine: (record) => !this.props.readonly && !this.isRecordReadonly(record),
        });
    },

    /**
     * The bundle or section, around this line, that prints it as part of one row.
     */
    twpGroupOf(record) {
        let parent = this.parentSectionMap.get(record);
        while (parent) {
            if (twpGroups(parent)) {
                return parent;
            }
            parent = this.parentSectionMap.get(parent);
        }
        return null;
    },

    /**
     * A grouped section and its lines are marked, so what prints as one row reads as one block;
     * a line hidden on documents, or whose price is, is greyed.
     */
    getRowClass(record) {
        const classNames = [super.getRowClass(record)];
        if (this.isSection(record) && twpGroups(record)) {
            const data = record.data;
            const kind = data.twp_is_bundle
                ? "o_twp_bundle"
                : data.collapse_composition
                  ? "o_twp_one_line"
                  : "o_twp_one_price";
            classNames.push("o_twp_group", "o_twp_group_head", kind);
        } else if (this.twpGroupOf(record)) {
            classNames.push("o_twp_group", "o_twp_group_member");
        }
        if (!record.data.display_type && record.data.twp_hide_on_documents) {
            classNames.push("o_twp_hidden_line");
        }
        if (!record.data.display_type && record.data.twp_hide_price) {
            classNames.push("o_twp_hidden_price");
        }
        return classNames.join(" ");
    },

    /**
     * A bundle's row keeps its Bundle Qty cell, and an alternative's or add-on's its Option
     * cells. The columns sit just left of the section total on quotes, and last on templates,
     * so the cells a section row keeps stay together at the end and the title's colspan still
     * lines them up. All of them are kept together, each empty where it does not apply.
     */
    getSectionColumns(columns, record) {
        const sectionColumns = super.getSectionColumns(columns, record);
        const isOption = record.data.twp_option_mode && record.data.twp_option_mode !== "included";
        const extra = TWP_SECTION_COLUMNS.filter((name) => columns.some((col) => col.name === name));
        if (!(record.data.twp_is_bundle || isOption) || !extra.length) {
            return sectionColumns;
        }
        const names = new Set([...sectionColumns.map((col) => col.name), ...extra]);
        const kept = columns.filter((col) => col.widget === "handle" || names.has(col.name));
        return kept.map((col) =>
            col.name === this.titleField
                ? { ...col, colspan: columns.length - kept.length + 1 }
                : { ...col }
        );
    },
});

patch(SaleOrderLineListRenderer.prototype, {
    setup() {
        super.setup();
        this.copyFields.push(
            "twp_is_bundle",
            "twp_bundle_qty",
            "twp_option_mode",
            "twp_option_group",
            "twp_option_chosen",
            "twp_qty_per_bundle",
            "twp_hide_on_documents",
            "twp_hide_price"
        );
    },

    /**
     * A bundle reuses Odoo's Hide Prices for its members; the server enforces the same.
     */
    async twpToggleBundle(record) {
        const isBundle = !record.data.twp_is_bundle;
        await record.update({
            twp_is_bundle: isBundle,
            collapse_prices: isBundle,
            collapse_composition: false,
        });
    },

    async twpSetOptionMode(record, mode) {
        await record.update({ twp_option_mode: mode, twp_option_chosen: false });
    },

    /**
     * Options are settled when the order is confirmed; the server refuses changes after.
     */
    twpOptionsLocked(record) {
        const state = record.model.root?.data?.state;
        return Boolean(state) && !["draft", "sent"].includes(state);
    },

    /**
     * An itemized quote takes no new bundles, and no alternatives or add-ons unless it allows
     * them. The server warns about any already there, and refuses to print, send or confirm.
     */
    twpItemized(record) {
        return record.model.root?.data?.twp_structure === "itemized";
    },

    /**
     * Odoo's optional section, or one inside it, is offered to the customer online at quantity
     * 0, so it can be neither a bundle nor an option until it is unset. The server refuses both.
     */
    twpInOptional(record) {
        return this.shouldCollapse(record, "is_optional", true);
    },

    twpCanSetBundle(record) {
        return record.data.twp_is_bundle || (!this.twpItemized(record) && !this.twpInOptional(record));
    },

    twpCanSetOption(record) {
        return (
            !this.twpInOptional(record) &&
            (!this.twpItemized(record) || Boolean(record.model.root?.data?.twp_allow_options))
        );
    },

    /**
     * A chosen alternative unchooses the others in its set, as the server does on save, so
     * the total in the form is right before saving.
     */
    async twpToggleChosen(record) {
        const chosen = !record.data.twp_option_chosen;
        if (chosen && record.data.twp_option_mode === "alternative") {
            const group = record.data.twp_option_group || "";
            for (const other of this.props.list.records) {
                if (
                    other !== record &&
                    other.data.display_type &&
                    other.data.twp_option_mode === "alternative" &&
                    (other.data.twp_option_group || "") === group &&
                    other.data.twp_option_chosen
                ) {
                    await other.update({ twp_option_chosen: false });
                }
            }
        }
        await record.update({ twp_option_chosen: chosen });
    },

    /**
     * A line in the bundle with the company's adjustment product, hidden on documents. The
     * server's default_get fills it in from the context.
     */
    async twpAddAdjustment(record) {
        this.twpAdjustment = true;
        try {
            await this.addRowInSection(record, false);
        } finally {
            this.twpAdjustment = false;
        }
    },

    getInsertLineContext(record, addSubSection) {
        const context = super.getInsertLineContext(record, addSubSection);
        return this.twpAdjustment ? { ...context, twp_bundle_adjustment: true } : context;
    },
});

patch(SaleOrderTemplateLineListRenderer.prototype, {
    setup() {
        super.setup();
        this.copyFields.push("twp_is_bundle", "twp_bundle_qty", "twp_hide_on_documents", "twp_hide_price");
    },

    async twpToggleBundle(record) {
        await record.update({ twp_is_bundle: !record.data.twp_is_bundle });
    },
});
