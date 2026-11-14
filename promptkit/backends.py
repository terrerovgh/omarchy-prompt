"""LLM backends that run the rewrite. Each returns the parsed JSON object.

- cli           : a local AI CLI harness (Claude Code, Codex, Antigravity,
                  Kimi Code, pi, OpenCode, Hermes); see engines.py.
- anthropic     : the Claude API over HTTPS (raw HTTP; the plugin is stdlib-only).
- openai-compat : any /chat/completions endpoint (OpenAI, Gemini, Kimi,
                  DeepSeek, OpenRouter, Ollama, llama.cpp on the S24, ...).
"""
import json
import os
import re
import stat
import urllib.error
import urllib.request
from pathlib import Path

from . import engines

MAX_RESPONSE = 1024 * 1024
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2026-10-21"
# Models that accept server-side refusal fallbacks (fallbacks: "default").
FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class BackendError(Exception):
    pass


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
    # Several objects or prose around them: take the last complete object.
    decoder, found, i = json.JSONDecoder(), None, text.find("{")
    while i >= 0:
        try:
            obj, length = decoder.raw_decode(text, i)
            if isinstance(obj, dict):
                found = obj
            i = text.find("{", i + length)
        except ValueError:
            i = text.find("{", i + 1)
    if found is not None:
        return found
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


BACKENDS = {"anthropic": anthropic, "openai-compat": openai_compat}


def terminate_child():
    engines.terminate_child()


def _api_ready(profile):
    """API profiles show up only when they can work: a key is present, or
    a keyless (local) profile was explicitly enabled."""
    if profile.get("type") == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return True
    key = profile.get("api_key_file")
    if key:
        return Path(os.path.expanduser(key)).is_file()
    return bool(profile.get("enabled"))


def available(config, refresh=False):
    """Selectable rewriters: installed CLI engines first, then ready API profiles."""
    detected = engines.detect(refresh)
    out = []
    profiles = config.get("profiles", {})
    for name in engines.AUTO_ORDER:
        spec = engines.ENGINES[name]
        prof = profiles.get(name, {})
        info = detected.get(name, {})
        if not info.get("installed"):
            continue
        model = prof.get("model", spec["model"])
        label = prof.get("model_label") or (spec["model_label"] if model == spec["model"] else model) or "default"
        out.append({"id": name, "kind": "cli", "label": f"{spec['label']} · {label}", "short": spec["label"],
                    "version": info.get("version", ""),
                    "blocked": name == "hermes" and not prof.get("allow_tools")})
    for name, prof in profiles.items():
        if isinstance(prof, dict) and prof.get("type") in BACKENDS and _api_ready(prof):
            out.append({"id": name, "kind": "api", "label": f"{name} · {prof.get('model', '')}", "short": name,
                        "version": "", "blocked": False})
    return out


def resolve(config, backend_name=None):
    """Turn 'auto' (or nothing) into a concrete profile name."""
    name = backend_name or config.get("backend") or "auto"
    if name == "claude-cli":  # pre-1.1 name
        name = "claude"
    if name != "auto":
        return name
    for item in available(config):
        if not item["blocked"]:
            return item["id"]
    raise BackendError("no rewriter found: install Claude Code, Codex, Antigravity, Kimi Code, pi or OpenCode, "
                       "or configure an API profile")


def run(config, system, user, schema, backend_name=None):
    name = resolve(config, backend_name)
    profiles = config.get("profiles", {})
    profile = profiles.get(name)
    if profile is None and name in engines.ENGINES:
        profile = {"type": "cli"}
    if not isinstance(profile, dict):
        raise BackendError(f"unknown backend {name!r}")
    timeout = float(config.get("timeout") or 90)
    kind = profile.get("type", "cli")
    if kind == "cli":
        try:
            raw = engines.run(profile.get("engine", name), profile, system, user, schema, timeout)
        except engines.EngineError as e:
            raise BackendError(str(e)) from e
        return name, raw if isinstance(raw, dict) else extract_json(raw)
    fn = BACKENDS.get(kind)
    if not fn:
        raise BackendError(f"unknown backend type {kind!r}")
    return name, fn(profile, system, user, schema, timeout)
