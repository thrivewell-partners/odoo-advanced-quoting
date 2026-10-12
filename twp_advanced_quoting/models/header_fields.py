"""The quote's header fields, which each company can turn on or off and rename in Settings."""

# (field suffix, default label). The order field is `twp_<suffix>`; the company carries
# `twp_<suffix>_enabled` and `twp_<suffix>_label`.
HEADER_FIELDS = (
    ("job_name", "Job Name"),
    ("ship_via", "Ship Via"),
    ("fob", "FOB"),
    ("freight", "Freight"),
    ("lead_time", "Estimated Lead Time"),
)


def header_field_settings(company, suffixes=None):
    """[(field name, label, enabled)] for the company, in print order."""
    return [
        (f"twp_{suffix}", company[f"twp_{suffix}_label"] or default, company[f"twp_{suffix}_enabled"])
        for suffix, default in HEADER_FIELDS
        if suffixes is None or suffix in suffixes
    ]


def apply_header_field_settings(arch, company, suffixes=None):
    """Rename the header fields in a form arch, and hide the ones the company turned off."""
    for name, label, enabled in header_field_settings(company, suffixes):
        for node in arch.xpath(f"//field[@name='{name}']"):
            node.set("string", label)
            if not enabled:
                node.set("invisible", "1")
    return arch


def header_field_cache_key(company, suffixes=None):
    return tuple(header_field_settings(company, suffixes))
