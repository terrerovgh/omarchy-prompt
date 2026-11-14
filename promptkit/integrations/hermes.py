"""Hermes Agent (`hermes -z`): optional integration (adapter not run yet).

Hermes cannot run with its tools disabled, so even when installed it stays
blocked until profiles.hermes.allow_tools is true.
"""
from ..engines import EngineError, inline_prompt, text_parse

DESCRIPTION = "Hermes Agent, with its configured default model"
SAFETY = "cannot disable its tools: blocked until profiles.hermes.allow_tools is true"


def build(system, user, schema, model, tmp, opts):
    if not opts.get("allow_tools"):
        raise EngineError(
            "Hermes cannot run with its tools disabled, so it is off by default. "
            "Set profiles.hermes.allow_tools to true to use it anyway.")
    # Documented form: hermes -z "<instruction>" < context-file
    args = ["-z", "Follow the instructions in the text on stdin. Answer with the JSON object only.",
            "--ignore-rules", "--ignore-user-config"]
    if model:
        args += ["--model", model]
    return args, inline_prompt(system, user, schema)


ENGINE = {
    "label": "Hermes",
    "binaries": ["hermes"],
    "model": "",
    "model_label": "",
    "options": {},
    "build": build,
    "parse": text_parse,
}
