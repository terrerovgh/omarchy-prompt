"""Google Antigravity CLI (`agy`): optional integration.

Uses agy's default model unless profiles.antigravity.model is set, e.g.
`promptctl.py config set profiles.antigravity.model gemini-4-hydrogen-low`.
"""
import json

from ..engines import EngineError, inline_prompt

DESCRIPTION = "Antigravity CLI, with agy's default model"
SAFETY = ("headless mode auto-denies tools that need approval (shell, edits); "
          "--dangerously-skip-permissions is never passed; slash commands off")


def build(system, user, schema, model, tmp, opts):
    # The prompt goes in as one stream-json event on stdin.
    args = ["--input-format", "stream-json", "--output-format", "stream-json",
            "--disable-slash-commands", "--json-schema", json.dumps(schema)]
    if model:
        args += ["--model", model]
    event = {"event": "user", "message": {"content": inline_prompt(system, user, schema)}}
    return args + ["--print="], json.dumps(event) + "\n"


def parse(stdout):
    data = None
    for line in stdout.splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("event") == "result" and isinstance(msg.get("result"), dict):
            data = msg["result"]
        elif isinstance(msg, dict) and "status" in msg and data is None:
            data = msg  # plain --output-format json
    if data is None:
        raise EngineError("antigravity returned no result")
    if data.get("status") not in (None, "SUCCESS"):
        raise EngineError(f"antigravity: {str(data.get('error') or data.get('status'))[:200]}")
    if isinstance(data.get("structured_output"), dict):
        return data["structured_output"]
    if not data.get("response") and data.get("denied_actions"):
        raise EngineError("antigravity tried to use a tool, which is blocked; no answer")
    return data.get("response", "")


ENGINE = {
    "label": "Antigravity",
    "binaries": ["agy", "antigravity"],
    "model": "",
    "model_label": "",
    "options": {},
    "build": build,
    "parse": parse,
}
