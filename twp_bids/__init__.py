from . import models
from . import wizard

# The Quotations actions this module keeps bids out of, and the domain each had before.
QUOTATION_ACTIONS = {
    "sale.action_quotations_with_onboarding": False,
    "sale.action_quotations": False,
    "sale.action_quotations_salesteams": "[]",
}


def uninstall_hook(env):
    for xmlid, domain in QUOTATION_ACTIONS.items():
        action = env.ref(xmlid, raise_if_not_found=False)
        if action:
            action.domain = domain
