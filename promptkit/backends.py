"""LLM backends that run the rewrite. Each returns the parsed JSON object.

- claude-cli    : the local Claude Code CLI (`claude -p`), using your login.
- anthropic     : the Claude API over HTTPS (raw HTTP; the plugin is stdlib-only).
- openai-compat : any /chat/completions endpoint (OpenAI, Gemini, Kimi,
                  DeepSeek, OpenRouter, Ollama, llama.cpp on the S24, ...).
"""
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

MAX_RESPONSE = 1024 * 1024
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2026-10-21"
# Models that accept server-side refusal fallbacks (fallbacks: "default").
FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class BackendError(Exception):
    pass


# The running claude subprocess, so a SIGTERM to promptctl can stop it too.
CHILD = None


def terminate_child():
    child = CHILD
    if child is not None and child.poll() is None:
        child.terminate()


def read_key(path_str, env_var=None):
    if env_var and os.environ.get(env_var):
        return os.environ[env_var].strip()
    if not path_str:
        return ""
    path = Path(os.path.expanduser(path_str))
    if not path.exists():
        raise BackendError(f"API key file not found: {path}")
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise BackendError(f"{path} is readable by others; run: chmod 600 {path}")
    return path.read_text(encoding="utf-8").strip()


def extract_json(text):
    """Parse a JSON object from model text (tolerates fences, <think> blocks, prose)."""
    if not isinstance(text, str):
        raise BackendError("empty model response")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            pass
    raise BackendError("model did not return valid JSON")


def _http_json(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read(65536).decode("utf-8", "replace"))
            err = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(err, dict):
                detail = str(err.get("message", ""))[:200]
            elif isinstance(err, str):
                detail = err[:200]
        except (ValueError, OSError):
            pass
        raise BackendError(f"HTTP {e.code}{': ' + detail if detail else ''}") from e
    except urllib.error.URLError as e:
        raise BackendError(f"network: {e.reason}") from e
    except TimeoutError as e:
        raise BackendError("timeout") from e
    if len(raw) > MAX_RESPONSE:
        raise BackendError("response too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as e:
        raise BackendError("invalid JSON from server") from e


# ---------------------------------------------------------------- claude-cli

def _find_claude(command):
    if os.path.isabs(os.path.expanduser(command)):
        path = os.path.expanduser(command)
        return path if os.access(path, os.X_OK) else None
    found = shutil.which(command)
    if found:
        return found
    # The shell's environment often lacks mise/npm paths.
    home = Path.home()
    for candidate in (
        home / ".local/share/mise/shims" / command,
        home / ".local/share/mise/command-wrappers/bin" / command,
        home / ".local/bin" / command,
        home / ".claude/local" / command,
    ):
        if os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def claude_cli(profile, system, user, schema, timeout):
    binary = _find_claude(profile.get("command") or "claude")
    if not binary:
        raise BackendError("claude CLI not found (set profiles.claude-cli.command)")
    cmd = [
        binary, "-p",
        "--tools", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--setting-sources", "",
        "--output-format", "json",
        "--system-prompt", system,
        "--json-schema", json.dumps(schema),
    ]
    if profile.get("model"):
        cmd += ["--model", str(profile["model"])]
    if profile.get("effort"):
        cmd += ["--effort", str(profile["effort"])]
    env = dict(os.environ)
    path_dirs = [str(Path.home() / ".local/share/mise/shims"), str(Path.home() / ".local/bin")]
    env["PATH"] = os.pathsep.join(path_dirs + [env.get("PATH", "/usr/bin:/bin")])
    global CHILD
    with tempfile.TemporaryDirectory(prefix="omarchy-prompt-") as cwd:
        CHILD = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, cwd=cwd, env=env)
        try:
            stdout, stderr = CHILD.communicate(user, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            CHILD.kill()
            CHILD.communicate()
            raise BackendError("timeout") from e
        finally:
            returncode, CHILD = CHILD.returncode, None
    try:
        data = json.loads(stdout)
    except ValueError:
        tail = (stderr or stdout or "").strip().splitlines()[-1:] or ["no output"]
        raise BackendError(f"claude exited {returncode}: {tail[0][:200]}")
    if data.get("is_error"):
        raise BackendError(f"claude: {str(data.get('result') or data.get('subtype'))[:200]}")
    if isinstance(data.get("structured_output"), dict):
        return data["structured_output"]
    return extract_json(data.get("result", ""))


# ----------------------------------------------------------------- anthropic

def anthropic(profile, system, user, schema, timeout):
    key = read_key(profile.get("api_key_file", ""), "ANTHROPIC_API_KEY")
    if not key:
        raise BackendError("no Anthropic API key (ANTHROPIC_API_KEY or profiles.anthropic.api_key_file)")
    model = profile.get("model") or "claude-opus-5-5"
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if profile.get("effort"):
        output_config["effort"] = profile["effort"]
    body = {
        "model": model,
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": output_config,
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    if model in FALLBACK_MODELS:
        body["fallbacks"] = "default"
        headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
    data = _http_json(profile.get("base_url") or ANTHROPIC_URL, body, headers, timeout)
    stop = data.get("stop_reason")
    if stop == "refusal":
        raise BackendError("the model declined this request")
    if stop == "max_tokens":
        raise BackendError("response was cut off (max_tokens)")
    texts = [b.get("text", "") for b in data.get("content", []) if isinstance(b, dict) and b.get("type") == "text"]
    return extract_json("".join(texts))


# ------------------------------------------------------------- openai-compat

def openai_compat(profile, system, user, schema, timeout):
    base = (profile.get("base_url") or "").rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise BackendError("profile base_url must be http(s)")
    key = read_key(profile.get("api_key_file", ""))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    schema_hint = "Respond with a single JSON object matching this JSON Schema:\n" + json.dumps(schema)
    body = {
        "model": profile.get("model") or "",
        "messages": [
            {"role": "system", "content": system + "\n\n" + schema_hint},
            {"role": "user", "content": user},
        ],
    }
    if profile.get("json_mode", True):
        body["response_format"] = {"type": "json_object"}
    data = _http_json(base + "/chat/completions", body, headers, timeout)
    try:
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        raise BackendError("unexpected response shape") from e
    if choice.get("finish_reason") == "length":
        raise BackendError("response was cut off (length)")
    return extract_json(content)


BACKENDS = {"claude-cli": claude_cli, "anthropic": anthropic, "openai-compat": openai_compat}


def run(config, system, user, schema, backend_name=None):
    name = backend_name or config.get("backend") or "claude-cli"
    profile = config.get("profiles", {}).get(name)
    if not isinstance(profile, dict):
        raise BackendError(f"unknown backend profile {name!r}")
    fn = BACKENDS.get(profile.get("type", name))
    if not fn:
        raise BackendError(f"unknown backend type {profile.get('type')!r}")
    timeout = float(config.get("timeout") or 90)
    return name, fn(profile, system, user, schema, timeout)
