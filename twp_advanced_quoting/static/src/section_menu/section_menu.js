import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { SaleOrderLineListRenderer } from "@sale/js/sale_order_line_field/sale_order_line_field";
import { SaleOrderTemplateLineListRenderer } from "@sale_management/fields/sale_order_template_line_field/sale_order_template_line_field";
import { patch } from "@web/core/utils/patch";

patch(SectionAndNoteListRenderer.prototype, {
    /**
     * A bundle's row keeps its Bundle Qty cell. The column sits just left of the section
     * total on quotes, and last on templates, so the cells a section row keeps stay together
     * at the end and the title's colspan still lines them up.
     */
    getSectionColumns(columns, record) {
        const sectionColumns = super.getSectionColumns(columns, record);
        if (!record.data.twp_is_bundle || !columns.some((col) => col.name === "twp_bundle_qty")) {
            return sectionColumns;
        }
        const names = new Set([...sectionColumns.map((col) => col.name), "twp_bundle_qty"]);
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
        await record.update({ twp_option_mode: mode });
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
