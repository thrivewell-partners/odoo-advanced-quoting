import { registry } from "@web/core/registry";

const OPTION_ONE = ".o_twp_m_group:has(.o_twp_m_title:contains('Option 1'))";
const BUNDLE = ".o_twp_m_group.o_twp_m_bundle";

registry.category("web_tour.tours").add("twp_mobile_lines", {
    steps: () => [
        // The bundle opens with its lines; the options start folded, as a set to choose from.
        { trigger: `${BUNDLE} .o_twp_m_badge_kind:contains('Bundle')` },
        { trigger: `${BUNDLE} .o_twp_m_inner .o_kanban_record:contains('TWP Bracket'):contains('Per Bundle')` },
        { trigger: `${BUNDLE} .o_kanban_record:contains('TWP Labor') .o_twp_m_tags:contains('Hidden on documents')` },
        { trigger: `.o_twp_m_choose:contains('Choose one')` },
        { trigger: `.o_twp_m_or` },
        { trigger: `${OPTION_ONE}.o_twp_m_folded:not(:has(.o_twp_m_inner))` },
        { trigger: `.o_twp_m_group.o_twp_m_addon.o_twp_m_folded` },
        // Unfolded, an option shows its lines.
        { trigger: `${OPTION_ONE} .o_twp_m_fold`, run: "click" },
        { trigger: `${OPTION_ONE} .o_twp_m_inner .o_kanban_record:contains('TWP Option One')` },
        // Its menu chooses it, as the desktop's does.
        { trigger: `${OPTION_ONE} .o_twp_m_menu`, run: "click" },
        { trigger: ".o-dropdown-item:contains('Mark Chosen')", run: "click" },
        { trigger: `${OPTION_ONE} .o_twp_m_badge_chosen:contains('Chosen')` },
        // One more bundle: its lines follow.
        { trigger: `${BUNDLE} .o_twp_m_stepper button[aria-label='One more bundle']`, run: "click" },
        { trigger: `${BUNDLE} .o_twp_m_stepper span:contains('6')` },
        { trigger: `${BUNDLE} .o_kanban_record:contains('TWP Bracket'):contains('18.00')` },
        // The eye prints the hidden labor line again, without opening it.
        { trigger: `${BUNDLE} .o_kanban_record:contains('TWP Labor') .o_twp_print_toggle`, run: "click" },
        { trigger: `${BUNDLE} .o_kanban_record:contains('TWP Labor'):not(:has(.o_twp_m_tags))` },
        { trigger: ".o_form_button_save", run: "click" },
        { trigger: ".o_form_saved" },
    ],
});
