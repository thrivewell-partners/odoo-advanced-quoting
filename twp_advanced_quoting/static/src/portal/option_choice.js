import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * The customer's choice of alternatives and add-ons on the online quote. Each click saves it, and
 * the page reloads so the totals, the tags and the Sign button follow, as Sales' own optional
 * lines do.
 */
export class TwpOptionChoice extends Interaction {
    static selector = "#sales_order_table";
    dynamicContent = {
        "button.twp_option_choose": {
            "t-on-click.prevent.withTarget": this.onChoose,
        },
    };

    async onChoose(ev, button) {
        button.disabled = true;
        await this.waitFor(rpc(`/my/orders/${this.el.dataset.orderId}/twp_option`, {
            access_token: this.el.dataset.token,
            line_id: parseInt(button.dataset.lineId),
            chosen: button.dataset.chosen === "1",
        }));
        window.location.reload();
    }
}

registry.category("public.interactions").add("twp_advanced_quoting.option_choice", TwpOptionChoice);
