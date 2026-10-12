import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { SaleOrderLineListRenderer } from "@sale/js/sale_order_line_field/sale_order_line_field";
import { SaleOrderTemplateLineListRenderer } from "@sale_management/fields/sale_order_template_line_field/sale_order_template_line_field";
import { patch } from "@web/core/utils/patch";

// Cells a bundle's or an option's row keeps beside its section total.
const TWP_SECTION_COLUMNS = ["twp_option_group", "twp_option_label", "twp_bundle_qty"];

patch(SectionAndNoteListRenderer.prototype, {
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
