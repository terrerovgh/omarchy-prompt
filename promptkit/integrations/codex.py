"""OpenAI Codex (`codex exec`): built-in engine."""
import json
from pathlib import Path

from ..engines import inline_prompt, text_parse

DESCRIPTION = "Codex with GPT-6 Luna"
SAFETY = "--sandbox read-only (no writes, no network), --ephemeral (no saved session)"


def build(system, user, schema, model, tmp, opts):
    schema_file = Path(tmp) / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    args = ["exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
            "--output-schema", str(schema_file)]
    if model:
        args += ["--model", model]
    return args + ["-"], inline_prompt(system, user, schema)


ENGINE = {
    "label": "Codex",
    "binaries": ["codex"],
    "model": "gpt-6-luna",
    "model_label": "GPT-6 Luna",
    "options": {},
    "build": build,
    "parse": text_parse,
}
