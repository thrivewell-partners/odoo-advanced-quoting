import { AccountProductCatalogSearchPanel } from "@account/components/product_catalog/search/search_panel";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

// The quote's catalog lists subsections under their section, so Option 1 and Option 2 or a
// bundle can be added to directly. Only a top-level group is dragged, with all it holds.
patch(AccountProductCatalogSearchPanel.prototype, {
    async loadSections() {
        // Odoo's, keeping each group's depth.
        if (!this.showSections) {
            return;
        }
        const sections = await rpc("/product/catalog/get_sections", this._getSectionInfoParams());
        this.state.sections = new Map(
            sections.map(({ id, name, sequence, line_count, depth }) => [
                id,
                { name, sequence, line_count, depth: depth || 0 },
            ])
        );
        this.setSelectedSection(this.state.sections.size > 0 ? [...this.state.sections.keys()][0] : null);
    },

    twpIsSubsection(sectionId) {
        return Boolean(this.state.sections.get(sectionId)?.depth);
    },

    onDrop(targetSecId, ev) {
        if (this.twpIsSubsection(targetSecId)) {
            ev.preventDefault();
            return;
        }
        super.onDrop(targetSecId, ev);
    },
});
