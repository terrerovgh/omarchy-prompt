"""Claude Code (`claude -p`): built-in engine."""
import json

from ..engines import EngineError

DESCRIPTION = "Claude Code with Sonnet 5.5"
SAFETY = '--tools "" (no tools), no MCP servers, no settings files, no saved session'


def build(system, user, schema, model, tmp, opts):
    args = [
        "-p",
        "--tools", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--setting-sources", "",
        "--output-format", "json",
        "--system-prompt", system,
        "--json-schema", json.dumps(schema),
    ]
    if model:
        args += ["--model", model]
    if opts.get("effort"):
        args += ["--effort", str(opts["effort"])]
    return args, user


def parse(stdout):
    data = json.loads(stdout)
    if data.get("is_error"):
        raise EngineError(f"claude: {str(data.get('result') or data.get('subtype'))[:200]}")
    if isinstance(data.get("structured_output"), dict):
        return data["structured_output"]
    return data.get("result", "")


ENGINE = {
    "label": "Claude",
    "binaries": ["claude"],
    "model": "claude-sonnet-5-5",
    "model_label": "Sonnet 5.5",
    "options": {"effort": "low"},
    "build": build,
    "parse": parse,
}
