import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * An eye on each line: open when the line prints, crossed out when it is hidden on documents.
 * One click flips it, without opening the row, so a single line in a bundle can be left off.
 */
export class TwpPrintToggle extends Component {
    static template = "twp_advanced_quoting.PrintToggle";
    static props = { ...standardFieldProps };

    get hidden() {
        return Boolean(this.props.record.data[this.props.name]);
    }

    get tooltip() {
        return this.hidden
            ? _t("Hidden on documents, still in the total. Click to print it.")
            : _t("Prints on documents. Click to hide it.");
    }

    toggle() {
        if (!this.props.readonly) {
            this.props.record.update({ [this.props.name]: !this.hidden });
        }
    }
}

registry.category("fields").add("twp_print_toggle", {
    component: TwpPrintToggle,
    displayName: _t("Print Toggle"),
    supportedTypes: ["boolean"],
});
