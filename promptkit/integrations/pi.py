"""pi coding agent (`pi -p`): optional integration.

Uses pi's own default model unless profiles.pi.model is set, e.g.
`promptctl.py config set profiles.pi.model deepseek/deepseek-flash`.
"""
from ..engines import schema_hint, text_parse

DESCRIPTION = "pi, with the model configured in pi"
SAFETY = "--no-tools, --no-session, --no-context-files, --no-mcp, --no-extensions"


def build(system, user, schema, model, tmp, opts):
    args = [
        "-p", "--no-tools", "--no-session", "--no-extensions", "--no-mcp", "--no-skills",
        "--no-prompt-templates", "--no-context-files", "--no-approve", "--offline",
        "--system-prompt", system + "\n\n" + schema_hint(schema),
    ]
    if model:
        args += ["--model", model]
    if opts.get("thinking"):
        args += ["--thinking", str(opts["thinking"])]
    return args, user


ENGINE = {
    "label": "pi",
    "binaries": ["pi"],
    "model": "",
    "model_label": "",
    "options": {"thinking": "low"},
    "build": build,
    "parse": text_parse,
}
