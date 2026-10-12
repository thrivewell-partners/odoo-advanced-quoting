import { SaleOrderLineListRenderer } from "@sale/js/sale_order_line_field/sale_order_line_field";
import { patch } from "@web/core/utils/patch";

patch(SaleOrderLineListRenderer.prototype, {
    setup() {
        super.setup();
        this.copyFields.push(
            "twp_is_bundle",
            "twp_bundle_qty",
            "twp_option_mode",
            "twp_option_group",
            "twp_option_chosen"
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
});
