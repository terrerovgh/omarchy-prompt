"""OpenCode (`opencode run`): optional integration (adapter not run yet)."""
import json
from pathlib import Path

from ..engines import FIXED_ASK, schema_hint, text_parse

DESCRIPTION = "OpenCode, with its configured default model"
SAFETY = "temporary agent whose permissions deny every action"


def build(system, user, schema, model, tmp, opts):
    # Project config in the private temp dir: a primary agent whose system
    # prompt holds our instructions and the material, and which may do nothing.
    agent = {"mode": "primary", "system": system + "\n\n" + schema_hint(schema) + "\n\n" + user,
             "permissions": [{"action": "*", "resource": "*", "effect": "deny"}]}
    cfg = {"$schema": "https://opencode.ai/config.json", "default_agent": "rewriter", "agents": {"rewriter": agent}}
    if model:
        cfg["model"] = model
    (Path(tmp) / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
    return ["run", FIXED_ASK], None


ENGINE = {
    "label": "OpenCode",
    "binaries": ["opencode"],
    "model": "",
    "model_label": "",
    "options": {},
    "build": build,
    "parse": text_parse,
}
