"""OpenAI Codex (`codex exec`): built-in engine.

`--sandbox read-only` alone still lets Codex run shell commands that *read*
files, so selected text that talks the model into it could pull other files
into the rewrite. The run therefore also:

* disables every feature that gives the model a tool: the shell, unified
  exec and the code-mode host (with these off, Codex's `exec` tool fails
  closed for the agent and any sub-agent it spawns), plus apps, plugins,
  hooks, browser and computer use, image tools, goals, skills and memories;
* ignores the user's config.toml and exec-policy rules, so no MCP server or
  hook from there is loaded (authentication still comes from CODEX_HOME);
* turns off web search;
* emits JSONL events, and `parse` rejects the whole run if any event shows a
  tool call, so even an unexpected tool result can never reach the output
  or the history.
"""
import json
from pathlib import Path

from ..engines import inline_prompt

DESCRIPTION = "Codex with GPT-6 Luna"
SAFETY = ("tool features disabled (shell, unified exec, code mode, apps, plugins, hooks, browser), "
          "user config and rules ignored, web search off, --sandbox read-only, --ephemeral; "
          "any tool call discards the result")

DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "code_mode_host", "apps", "plugins", "hooks",
    "browser_use", "browser_use_external", "in_app_browser", "computer_use",
    "image_generation", "view_image", "multi_agent", "goals", "sleep_tool",
    "tool_suggest", "skill_search", "skill_mcp_dependency_install", "memories",
)

# JSONL item types that carry text only; anything else is a tool call.
TEXT_ITEMS = {"agent_message", "reasoning", "error", "todo_list"}


def build(system, user, schema, model, tmp, opts):
    schema_file = Path(tmp) / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    args = ["exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
            "--ignore-user-config", "--ignore-rules", "-c", 'web_search="disabled"']
    for feature in DISABLED_FEATURES:
        args += ["--disable", feature]
    args += ["--json", "--output-schema", str(schema_file)]
    if model:
        args += ["--model", model]
    return args + ["-"], inline_prompt(system, user, schema)


def parse(stdout):
    """Text of the last agent message; refuses runs that used any tool."""
    last = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind not in TEXT_ITEMS:
            raise ValueError(f"Codex called a tool ({kind}); result discarded")
        if kind == "agent_message" and event.get("type") == "item.completed":
            last = item.get("text") or ""
    if last is None:
        raise ValueError("no agent message")
    return last


ENGINE = {
    "label": "Codex",
    "binaries": ["codex"],
    "model": "gpt-6-luna",
    "model_label": "GPT-6 Luna",
    "options": {},
    "build": build,
    "parse": parse,
}
