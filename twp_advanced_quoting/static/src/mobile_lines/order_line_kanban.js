import { onWillRender, useState, useSubEnv } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { formatMonetary } from "@web/views/fields/formatters";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import {
    SaleOrderLineListRenderer,
    SaleOrderLineOne2Many,
} from "@sale/js/sale_order_line_field/sale_order_line_field";

/**
 * On a phone, Odoo shows the quote lines as cards, not the list, so the list's bundles and options
 * are drawn again here: each bundle or option a shaded block that folds, its lines as cards inside.
 */

// What each quote's phone has folded, until the page is reloaded (the app closed).
const foldMemory = new Map();

// The list's own actions, so the phone's menu does exactly what the desktop's does.
const BORROWED = [
    "buildParentSectionMap",
    "isSection",
    "isTopSection",
    "isSubSection",
    "shouldCollapse",
    "addRowInSection",
    "getInsertLineContext",
    "twpToggleBundle",
    "twpSetOptionMode",
    "twpOptionsLocked",
    "twpItemized",
    "twpInOptional",
    "twpCanSetBundle",
    "twpCanSetOption",
    "twpToggleChosen",
    "twpAddAdjustment",
    "twpCanAddStandalone",
    "twpAddStandalone",
];

function isOption(record) {
    return Boolean(record.data.display_type) && record.data.twp_option_mode !== "included";
}

function isGroup(record) {
    return Boolean(record.data.twp_is_bundle) || isOption(record);
}

export class TwpOrderLineKanbanRenderer extends KanbanRenderer {
    static template = "twp_advanced_quoting.OrderLineKanbanRenderer";
    static components = { ...KanbanRenderer.components, Dropdown, DropdownItem };

    setup() {
        super.setup();
        this.parentSectionMap = new Map();
        onWillRender(() => this.buildParentSectionMap());
        const root = this.props.list.model.root;
        const key = root?.resId ? `${root.resModel},${root.resId}` : null;
        if (key && !foldMemory.has(key)) {
            foldMemory.set(key, {});
        }
        this.folds = useState(key ? foldMemory.get(key) : {});
        // The print toggle changes a line without opening it, so it asks the lines.
        useSubEnv({ twpCanChangeLine: () => this.twpCanEdit });
    }

    get twpCanEdit() {
        return !this.props.readonly;
    }

    /**
     * Lines are rearranged on the desktop: dragging a card in or out of a group is not offered.
     */
    get canResequenceRecords() {
        return false;
    }

    // ------------------------------------------------------------
    // The lines as blocks
    // ------------------------------------------------------------

    /**
     * The lines as the quote prints them: sections, each holding its lines and subsections, and
     * each bundle or option a group around its own lines.
     */
    get twpBlocks() {
        const blocks = [];
        let section = null;
        let subsection = null;
        for (const record of this.props.list.records) {
            const type = record.data.display_type;
            if (type === "line_section") {
                section = this.twpBlock(record);
                subsection = null;
                blocks.push(section);
            } else if (type === "line_subsection" && section) {
                subsection = this.twpBlock(record);
                section.children.push(subsection);
            } else {
                const node = { kind: "line", record, key: record.id };
                (subsection || section)?.children.push(node);
                if (!section) {
                    blocks.push(node);
                }
            }
        }
        this.twpMarkChoices(blocks);
        for (const block of blocks) {
            this.twpMarkChoices(block.children || []);
        }
        return blocks;
    }

    twpBlock(record) {
        let kind = "section";
        if (record.data.twp_standalone) {
            kind = "standalone";
        } else if (isGroup(record)) {
            kind = "group";
        }
        return { kind, record, key: record.id, children: [] };
    }

    /**
     * "Choose one" heads a set of alternatives, and "or" stands between them, as on the PDF.
     */
    twpMarkChoices(nodes) {
        let previous = null;
        for (const node of nodes) {
            const data = node.record.data;
            if (node.kind === "group" && data.twp_option_mode === "alternative") {
                const group = data.twp_option_group || "";
                const sameSet =
                    previous?.kind === "group" &&
                    previous.record.data.twp_option_mode === "alternative" &&
                    (previous.record.data.twp_option_group || "") === group;
                node.chooseOne = !sameSet;
                node.orBefore = sameSet;
            }
            previous = node;
        }
    }

    /**
     * The product lines under a node. `inTotal` leaves out those in an alternative or add-on not
     * chosen, as the order total does.
     */
    twpLines(node, inTotal = false) {
        const lines = [];
        for (const child of node.children) {
            if (child.kind === "line") {
                if (!child.record.data.display_type) {
                    lines.push(child.record);
                }
            } else if (!(inTotal && isOption(child.record) && !child.record.data.twp_option_chosen)) {
                lines.push(...this.twpLines(child, inTotal));
            }
        }
        return lines;
    }

    /**
     * A bundle's or an option's own amount, chosen or not; a section's counts only what is in
     * the order total.
     */
    twpTotal(node) {
        const lines = this.twpLines(node, node.kind !== "group");
        const total = lines.reduce((sum, line) => sum + (line.data.price_subtotal || 0), 0);
        return formatMonetary(total, { currencyId: node.record.data.currency_id?.id });
    }

    twpItemCount(node) {
        const count = this.twpLines(node).length;
        return count === 1 ? _t("1 item") : _t("%s items", count);
    }

    // ------------------------------------------------------------
    // Folding
    // ------------------------------------------------------------

    twpFoldKey(record) {
        return String(record.resId || record.id);
    }

    /**
     * Options start folded, so a quote's choices read as a short list; bundles start open.
     */
    twpIsFolded(record) {
        const key = this.twpFoldKey(record);
        return key in this.folds ? this.folds[key] : isOption(record);
    }

    twpToggleFold(record) {
        this.folds[this.twpFoldKey(record)] = !this.twpIsFolded(record);
    }

    // ------------------------------------------------------------
    // A group's head
    // ------------------------------------------------------------

    twpKindLabel(record) {
        if (record.data.twp_is_bundle) {
            return _t("Bundle");
        }
        return record.data.twp_option_mode === "alternative" ? _t("Alternative") : _t("Add-on");
    }

    twpKindClass(record) {
        if (record.data.twp_is_bundle) {
            return "o_twp_m_bundle";
        }
        if (record.data.twp_option_chosen) {
            return record.data.twp_option_mode === "alternative" ? "o_twp_m_alternative" : "o_twp_m_addon";
        }
        return record.data.twp_option_mode === "alternative" ? "o_twp_m_off" : "o_twp_m_addon";
    }

    /**
     * Chosen or Not chosen beside the kind, once there is one to say.
     */
    twpStatus(record) {
        if (!isOption(record)) {
            return "";
        }
        if (record.data.twp_not_chosen) {
            return _t("Not chosen");
        }
        return record.data.twp_option_chosen ? _t("Chosen") : "";
    }

    twpInTotal(record) {
        if (!isOption(record)) {
            return "";
        }
        if (record.data.twp_option_chosen) {
            return _t("in the total");
        }
        return record.data.twp_option_mode === "addon" ? _t("not in the total until added") : _t("not in the total");
    }

    async twpStepBundle(record, step) {
        const qty = (record.data.twp_bundle_qty || 0) + step;
        if (qty >= 1) {
            await record.update({ twp_bundle_qty: qty });
        }
    }

    // ------------------------------------------------------------
    // The menu
    // ------------------------------------------------------------

    /**
     * The section menu's own items, as the desktop list offers them.
     */
    twpMenuItems(record) {
        if (!this.twpCanEdit) {
            return [];
        }
        const items = [];
        if (this.twpCanSetBundle(record)) {
            items.push({
                key: "bundle",
                icon: "fa-cube",
                label: record.data.twp_is_bundle ? _t("Unset Bundle") : _t("Set Bundle"),
                run: () => this.twpToggleBundle(record),
            });
        }
        if (record.data.twp_is_bundle) {
            items.push({
                key: "adjustment",
                icon: "fa-wrench",
                label: _t("Add Adjustment"),
                run: () => this.twpAddAdjustment(record),
            });
        }
        if (this.twpCanAddStandalone(record)) {
            items.push({
                key: "standalone",
                icon: "fa-level-up",
                label: _t("Add Standalone Lines"),
                run: () => this.twpAddStandalone(record),
            });
        }
        if (!this.twpOptionsLocked(record)) {
            const mode = record.data.twp_option_mode;
            if (mode !== "included") {
                items.push({
                    key: "chosen",
                    icon: record.data.twp_option_chosen ? "fa-square-o" : "fa-check-square-o",
                    label: record.data.twp_option_chosen ? _t("Mark Not Chosen") : _t("Mark Chosen"),
                    run: () => this.twpToggleChosen(record),
                });
            }
            if (mode !== "alternative" && this.twpCanSetOption(record)) {
                items.push({
                    key: "alternative",
                    icon: "fa-random",
                    label: _t("Set Alternative"),
                    run: () => this.twpSetOptionMode(record, "alternative"),
                });
            }
            if (mode !== "addon" && this.twpCanSetOption(record)) {
                items.push({
                    key: "addon",
                    icon: "fa-plus-square-o",
                    label: _t("Set Add-on"),
                    run: () => this.twpSetOptionMode(record, "addon"),
                });
            }
            if (mode !== "included") {
                items.push({
                    key: "unset",
                    icon: "fa-undo",
                    label: mode === "alternative" ? _t("Unset Alternative") : _t("Unset Add-on"),
                    run: () => this.twpSetOptionMode(record, "included"),
                });
            }
        }
        items.push({
            key: "edit",
            icon: "fa-pencil",
            label: _t("Edit"),
            run: () => this.props.openRecord(record),
        });
        return items;
    }
}

// Looked up when called, not copied here: the section menu's patch adds the twp ones to the list
// after this file has loaded.
for (const name of BORROWED) {
    TwpOrderLineKanbanRenderer.prototype[name] = function (...args) {
        return SaleOrderLineListRenderer.prototype[name].apply(this, args);
    };
}

SaleOrderLineOne2Many.components = {
    ...SaleOrderLineOne2Many.components,
    KanbanRenderer: TwpOrderLineKanbanRenderer,
};
