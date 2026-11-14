"""Kimi Code (`kimi -p`): optional integration.

Uses Kimi Code's default_model unless profiles.kimi.model is set, e.g.
`promptctl.py config set profiles.kimi.model kimi-code/kimi-for-coding`.
"""
import json
from pathlib import Path

from ..engines import FIXED_ASK, EngineError, schema_hint

DESCRIPTION = "Kimi Code, with the model configured in Kimi Code"
SAFETY = "custom agent file with an empty tool list (tools: []); Kimi still records a session per run"


def build(system, user, schema, model, tmp, opts):
    # kimi takes no prompt on stdin, so the material rides in the agent file,
    # which lives in the private temp dir.
    agent = Path(tmp) / "prompt-rewriter.md"
    agent.write_text(
        "---\nname: prompt-rewriter\ndescription: Rewrites prompts for a target model. Has no tools.\n"
        "tools: []\n---\n" + system + "\n\n" + schema_hint(schema) + "\n\n" + user + "\n",
        encoding="utf-8",
    )
    args = ["--agent-file", str(agent), "--output-format", "stream-json", "-p", FIXED_ASK]
    if model:
        args = ["-m", model] + args
    return args, None


def parse(stdout):
    texts = []
    for line in stdout.splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
            texts.append(msg["content"])
    if not texts:
        raise EngineError("kimi returned no answer")
    return texts[-1]


ENGINE = {
    "label": "Kimi",
    "binaries": ["kimi"],
    "model": "",
    "model_label": "",
    "options": {},
    "build": build,
    "parse": parse,
}
