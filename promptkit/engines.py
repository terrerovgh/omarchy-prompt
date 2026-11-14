"""Local AI CLI harnesses that can run the rewrite: registry, detection, runner.

Each engine runs one non-interactive turn with **every tool disabled**: the
selected text is untrusted, so the harness must not be able to run commands
or write files even if the text asks it to. Each run happens in an empty
temporary directory, and no session is saved where the CLI allows that.

An engine counts as installed only when its binary answers `--version`.
Stale mise shims exist on disk but fail that check.
"""
import importlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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


# Fixed instruction for CLIs that need a prompt argument; the material itself
# goes through stdin or a file in the private temp dir, never through argv,
# where other local accounts could read it from /proc.
FIXED_ASK = ("Rewrite the prompt given in <original_prompt> in your instructions, following them. "
             "Answer with the JSON object only.")


def schema_hint(schema):
    return "Respond with only a single JSON object matching this JSON Schema, with no other text:\n" + json.dumps(schema)


def text_parse(stdout):
    return stdout


def inline_prompt(system, user, schema):
    """For CLIs without a system-prompt flag: instructions first, material last."""
    return f"{system}\n\n{schema_hint(schema)}\n\n{user}"


# ------------------------------------------------------------- integrations
# Each module in promptkit/integrations exposes ENGINE = {label, binaries,
# model, model_label, options, build, parse}:
#   build(system, user, schema, model, tmp, opts) -> (argv_after_binary, stdin_text)
#   parse(stdout) -> dict (structured) or str (text holding the JSON)

# Built-in engines, always loaded; also the "auto" preference order.
CORE = ("codex", "claude")
# Optional integrations: imported only once installed by the user.
OPTIONAL = ("pi", "kimi", "antigravity", "opencode", "hermes")
CATALOG = CORE + OPTIONAL

_loaded = {}


def module(engine_id):
    if engine_id not in CATALOG:
        raise EngineError(f"unknown engine {engine_id!r}")
    if engine_id not in _loaded:
        _loaded[engine_id] = importlib.import_module(f"{__package__}.integrations.{engine_id}")
    return _loaded[engine_id]


def spec(engine_id):
    return module(engine_id).ENGINE


def active(config):
    """Engines in use: the built-in ones plus the installed integrations."""
    installed = config.get("integrations") or []
    return list(CORE) + [e for e in OPTIONAL if e in installed]


# ---------------------------------------------------------------- detection

def _cache_path():
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base and os.path.isabs(base) else Path.home() / ".cache"
    return root / "omarchy-prompt" / "engines.json"


def _probe(engine_id):
    binary = find_binary(spec(engine_id)["binaries"])
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


def detect(engine_ids, refresh=False):
    """{id: {"installed", "binary", "version"}} for the given engines.

    A tool counts only if its binary answers --version (stale mise shims
    fail). Results are cached per engine for CACHE_TTL.
    """
    path = _cache_path()
    cache = {}
    try:
        cache = json.loads(path.read_text(encoding="utf-8")).get("engines", {})
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError, AttributeError):
        cache = {}
    now = time.time()
    fresh, todo = {}, []
    for eid in engine_ids:
        entry = cache.get(eid)
        ok = (not refresh and isinstance(entry, dict) and now - entry.get("time", 0) < CACHE_TTL
              and (not entry.get("installed") or os.access(entry.get("binary", ""), os.X_OK)))
        if ok:
            fresh[eid] = entry
        else:
            todo.append(eid)
    if todo:
        with ThreadPoolExecutor(max_workers=len(todo)) as pool:
            for eid, result in zip(todo, pool.map(_probe, todo)):
                result["time"] = now
                fresh[eid] = cache[eid] = result
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"engines": cache}), encoding="utf-8")
        except OSError:
            pass
    return {eid: fresh[eid] for eid in engine_ids}


# ---------------------------------------------------------------------- run

def run(engine_id, profile, system, user, schema, timeout):
    """Run one rewrite through a CLI engine; returns a dict or JSON-bearing text."""
    global CHILD
    spec_ = spec(engine_id)
    binary = find_binary([profile["command"]] if profile.get("command") else spec_["binaries"])
    if not binary:
        raise EngineError(f"{spec_['label']} is not installed")
    model = profile.get("model", spec_["model"])
    opts = dict(spec_.get("options", {}))
    opts.update({k: v for k, v in profile.items() if k in ("effort", "thinking", "allow_tools")})
    with tempfile.TemporaryDirectory(prefix="omarchy-prompt-") as tmp:
        args, stdin_text = spec_["build"](system, user, schema, model, tmp, opts)
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
        raise EngineError(f"{spec_['label']} exited {returncode}: {tail[0][:200]}")
    try:
        return spec_["parse"](stdout)
    except ValueError as e:
        raise EngineError(f"{spec_['label']}: unreadable output") from e
