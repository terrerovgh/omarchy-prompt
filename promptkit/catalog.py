"""Target-model catalog (models.json) and the bundled prompting guides."""
import json
import re

from . import paths

CATEGORIES = [
    "coding",
    "agentic",
    "writing",
    "analysis",
    "extraction",
    "summarization",
    "education",
    "business",
    "system-prompt",
    "image-gen",
    "other",
]


class CatalogError(ValueError):
    pass


def load(path=None):
    with open(path or paths.CATALOG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def resolve(target, catalog=None):
    """Return (family, version) dicts for 'family/version'."""
    catalog = catalog or load()
    if not isinstance(target, str) or "/" not in target:
        raise CatalogError(f"target must look like family/version, got {target!r}")
    fam_id, ver_id = target.split("/", 1)
    for family in catalog["families"]:
        if family["id"] == fam_id:
            for version in family["versions"]:
                if version["id"] == ver_id:
                    return family, version
            raise CatalogError(f"unknown version {ver_id!r} for {fam_id}")
    raise CatalogError(f"unknown model family {fam_id!r}")


_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def read_guide(family):
    """Return (body, reviewed) of a family's guide, without front matter."""
    name = family["guide"]
    if "/" in name or name.startswith("."):
        raise CatalogError("invalid guide name")
    text = (paths.GUIDES_DIR / name).read_text(encoding="utf-8")
    reviewed = ""
    match = _FRONT_MATTER.match(text)
    if match:
        for line in match.group(1).splitlines():
            if line.startswith("reviewed:"):
                reviewed = line.split(":", 1)[1].strip()
        text = text[match.end():]
    return text.strip(), reviewed


def public(catalog=None):
    """Catalog trimmed to what the UI needs."""
    catalog = catalog or load()
    return {
        "default": catalog.get("default", ""),
        "reviewed": catalog.get("reviewed", ""),
        "categories": CATEGORIES,
        "families": [
            {
                "id": f["id"],
                "label": f["label"],
                "versions": [{"id": v["id"], "label": v["label"]} for v in f["versions"]],
            }
            for f in catalog["families"]
        ],
    }
