"""Local AI CLI harnesses that can run the rewrite, and their detection.

Each engine runs one non-interactive turn with **every tool disabled**: the
selected text is untrusted, so the harness must not be able to run commands
or write files even if the text asks it to. Each run happens in an empty
temporary directory, and no session is saved where the CLI allows that.

An engine counts as installed only when its binary answers `--version`.
Stale mise shims exist on disk but fail that check.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import paths

CACHE_TTL = 6 * 3600
VERSION_TIMEOUT = 8


class EngineError(Exception):
    pass


# The running subprocess, so a SIGTERM to promptctl can stop it too.
CHILD = None


def terminate_child():
    child = CHILD
    if child is not None and child.poll() is None:
        child.terminate()


def _search_dirs():
    home = Path.home()
    return [
        home / ".local/share/mise/shims",
        home / ".local/share/mise/command-wrappers/bin",
        home / ".local/bin",
        home / ".kimi-code/bin",
        home / ".claude/local",
        home / ".opencode/bin",
        home / ".bun/bin",
        home / ".npm-global/bin",
        home / ".cargo/bin",
        Path("/usr/local/bin"),
        Path("/usr/bin"),
    ]


def find_binary(names):
    for name in names:
        if os.path.isabs(os.path.expanduser(name)):
            path = os.path.expanduser(name)
            if os.access(path, os.X_OK):
                return path
            continue
        found = shutil.which(name)
        if found:
            return found
        for d in _search_dirs():
            candidate = d / name
            if os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def _child_env():
    env = dict(os.environ)
    extra = [str(d) for d in _search_dirs()[:5]]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "/usr/bin:/bin")])
    env.setdefault("NO_COLOR", "1")
    return env


def _schema_hint(schema):
    return "Respond with only a single JSON object matching this JSON Schema, with no other text:\n" + json.dumps(schema)


# ------------------------------------------------------------------ engines
# build(system, user, schema, model, tmp) -> (argv_after_binary, stdin_text)
# parse(stdout) -> dict (structured) or str (text containing the JSON)

def _claude_build(system, user, schema, model, tmp, opts):
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


def _claude_parse(stdout):
    data = json.loads(stdout)
    if data.get("is_error"):
        raise EngineError(f"claude: {str(data.get('result') or data.get('subtype'))[:200]}")
    if isinstance(data.get("structured_output"), dict):
        return data["structured_output"]
    return data.get("result", "")


def _kimi_build(system, user, schema, model, tmp, opts):
    # A custom agent with an empty tool list: it can only answer in text.
    agent = Path(tmp) / "prompt-rewriter.md"
    agent.write_text(
        "---\nname: prompt-rewriter\ndescription: Rewrites prompts for a target model. Has no tools.\n"
        "tools: []\n---\n" + system + "\n\n" + _schema_hint(schema) + "\n",
        encoding="utf-8",
    )
    args = ["--agent-file", str(agent), "--output-format", "stream-json", "-p", user]
    if model:
        args = ["-m", model] + args
    return args, None


def _kimi_parse(stdout):
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


def _pi_build(system, user, schema, model, tmp, opts):
    args = [
        "-p", "--no-tools", "--no-session", "--no-extensions", "--no-mcp", "--no-skills",
        "--no-prompt-templates", "--no-context-files", "--no-approve", "--offline",
        "--system-prompt", system + "\n\n" + _schema_hint(schema),
    ]
    if model:
        args += ["--model", model]
    if opts.get("thinking"):
        args += ["--thinking", str(opts["thinking"])]
    return args, user


def _text_parse(stdout):
    return stdout


def _inline_prompt(system, user, schema):
    # For CLIs without a system-prompt flag: instructions first, material last.
    return f"{system}\n\n{_schema_hint(schema)}\n\n{user}"


def _codex_build(system, user, schema, model, tmp, opts):
    # Read-only sandbox (no writes, no network), nothing saved to session history.
    schema_file = Path(tmp) / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    args = ["exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
            "--output-schema", str(schema_file)]
    if model:
        args += ["--model", model]
    return args + ["-"], _inline_prompt(system, user, schema)


def _agy_build(system, user, schema, model, tmp, opts):
    # Headless Antigravity soft-denies every tool that needs approval (shell,
    # edits) unless --dangerously-skip-permissions is given, which we never pass.
    args = ["-p", _inline_prompt(system, user, schema), "--output-format", "json"]
    if model:
        args += ["--model", model]
    return args, None


def _agy_parse(stdout):
    data = json.loads(stdout)
    if data.get("status") not in (None, "SUCCESS"):
        raise EngineError(f"antigravity: {str(data.get('error') or data.get('status'))[:200]}")
    return data.get("response", "")


def _opencode_build(system, user, schema, model, tmp, opts):
    # Project config in the empty temp dir: a primary agent whose system prompt
    # is ours and whose permissions deny every action (shell, edit, read, web...).
    agent = {"mode": "primary", "system": system + "\n\n" + _schema_hint(schema),
             "permissions": [{"action": "*", "resource": "*", "effect": "deny"}]}
    cfg = {"$schema": "https://opencode.ai/config.json", "default_agent": "rewriter", "agents": {"rewriter": agent}}
    if model:
        cfg["model"] = model
    (Path(tmp) / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
    return ["run", user], None


def _hermes_build(system, user, schema, model, tmp, opts):
    if not opts.get("allow_tools"):
        raise EngineError(
            "Hermes cannot run with its tools disabled, so it is off by default. "
            "Set profiles.hermes.allow_tools to true to use it anyway.")
    args = ["-z", _inline_prompt(system, user, schema), "--ignore-rules", "--ignore-user-config"]
    if model:
        args += ["--model", model]
    return args, None


ENGINES = {
    "claude": {
        "label": "Claude",
        "binaries": ["claude"],
        "model": "claude-sonnet-5-5",
        "model_label": "Sonnet 5.5",
        "options": {"effort": "low"},
        "build": _claude_build,
        "parse": _claude_parse,
    },
    "kimi": {
        "label": "Kimi",
        "binaries": ["kimi"],
        "model": "kimi-code/kimi-for-coding",
        "model_label": "K2.8 Preview",
        "options": {},
        "build": _kimi_build,
        "parse": _kimi_parse,
    },
    "pi": {
        "label": "pi",
        "binaries": ["pi"],
        "model": "deepseek/deepseek-flash",
        "model_label": "DS Flash",
        "options": {"thinking": "low"},
        "build": _pi_build,
        "parse": _text_parse,
    },
    "codex": {
        "label": "Codex",
        "binaries": ["codex"],
        "model": "gpt-6-luna",
        "model_label": "GPT-6 Luna",
        "options": {},
        "build": _codex_build,
        "parse": _text_parse,
    },
    "antigravity": {
        "label": "Antigravity",
        "binaries": ["agy", "antigravity"],
        "model": "gemini-4-hydrogen-low",
        "model_label": "Gemini 4 Hydrogen",
        "options": {},
        "build": _agy_build,
        "parse": _agy_parse,
    },
    "opencode": {
        "label": "OpenCode",
        "binaries": ["opencode"],
        "model": "",
        "model_label": "default",
        "options": {},
        "build": _opencode_build,
        "parse": _text_parse,
    },
    "hermes": {
        "label": "Hermes",
        "binaries": ["hermes"],
        "model": "",
        "model_label": "default",
        "options": {},
        "build": _hermes_build,
        "parse": _text_parse,
    },
}

# Preference order for backend "auto".
AUTO_ORDER = ["claude", "codex", "antigravity", "kimi", "pi", "opencode", "hermes"]


# ---------------------------------------------------------------- detection

def _cache_path():
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base and os.path.isabs(base) else Path.home() / ".cache"
    return root / "omarchy-prompt" / "engines.json"


def _probe(engine_id):
    spec = ENGINES[engine_id]
    binary = find_binary(spec["binaries"])
    if not binary:
        return {"installed": False}
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True,
                              timeout=VERSION_TIMEOUT, env=_child_env(), cwd=tempfile.gettempdir())
    except (OSError, subprocess.TimeoutExpired):
        return {"installed": False, "binary": binary}
    out = (proc.stdout or proc.stderr or "").strip().splitlines()
    first = out[0][:80] if out else ""
    if proc.returncode != 0 or "not a valid shim" in (proc.stdout + proc.stderr):
        return {"installed": False, "binary": binary}
    return {"installed": True, "binary": binary, "version": first}


def detect(refresh=False):
    """{engine_id: {"installed": bool, "binary": str, "version": str}}, cached for CACHE_TTL."""
    path = _cache_path()
    if not refresh:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if (time.time() - cached.get("time", 0) < CACHE_TTL
                    and set(cached.get("engines", {})) == set(ENGINES)
                    and all(not e.get("installed") or os.access(e.get("binary", ""), os.X_OK)
                            for e in cached["engines"].values())):
                return cached["engines"]
        except (OSError, ValueError, AttributeError):
            pass
    with ThreadPoolExecutor(max_workers=len(ENGINES)) as pool:
        results = dict(zip(ENGINES, pool.map(_probe, ENGINES)))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"time": time.time(), "engines": results}), encoding="utf-8")
    except OSError:
        pass
    return results


# ---------------------------------------------------------------------- run

def run(engine_id, profile, system, user, schema, timeout):
    """Run one rewrite through a CLI engine; returns a dict or JSON-bearing text."""
    global CHILD
    spec = ENGINES.get(engine_id)
    if not spec:
        raise EngineError(f"unknown engine {engine_id!r}")
    binary = find_binary([profile["command"]] if profile.get("command") else spec["binaries"])
    if not binary:
        raise EngineError(f"{spec['label']} is not installed")
    model = profile.get("model", spec["model"])
    opts = dict(spec.get("options", {}))
    opts.update({k: v for k, v in profile.items() if k in ("effort", "thinking", "allow_tools")})
    with tempfile.TemporaryDirectory(prefix="omarchy-prompt-") as tmp:
        args, stdin_text = spec["build"](system, user, schema, model, tmp, opts)
        CHILD = subprocess.Popen([binary] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, cwd=tmp, env=_child_env())
        try:
            stdout, stderr = CHILD.communicate(stdin_text or "", timeout=timeout)
        except subprocess.TimeoutExpired as e:
            CHILD.kill()
            CHILD.communicate()
            raise EngineError("timeout") from e
        finally:
            returncode, CHILD = CHILD.returncode, None
    if returncode != 0 and not stdout.strip():
        tail = (stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise EngineError(f"{spec['label']} exited {returncode}: {tail[0][:200]}")
    try:
        return spec["parse"](stdout)
    except ValueError as e:
        raise EngineError(f"{spec['label']}: unreadable output") from e
