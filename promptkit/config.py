"""User configuration: ~/.config/omarchy-prompt/config.json.

The file only names key *files*; secrets never live in the config itself.
"""
import copy
import json
import os

from . import paths

DEFAULTS = {
    # "auto" = the first installed CLI in engines.AUTO_ORDER; or a profile name.
    "backend": "auto",
    "ui_lang": "es",
    "last_target": "",
    "timeout": 90,
    "profiles": {
        # Local CLI harnesses (detected automatically). Override "model" here.
        "claude": {"type": "cli", "engine": "claude"},
        "codex": {"type": "cli", "engine": "codex"},
        "antigravity": {"type": "cli", "engine": "antigravity"},
        "kimi": {"type": "cli", "engine": "kimi"},
        "pi": {"type": "cli", "engine": "pi"},
        "opencode": {"type": "cli", "engine": "opencode"},
        "hermes": {"type": "cli", "engine": "hermes", "allow_tools": False},
        # HTTP APIs: offered once their key file exists (local ones need "enabled": true).
        "anthropic-api": {
            "type": "anthropic",
            "model": "claude-opus-5-5",
            "effort": "low",
            "api_key_file": "~/.config/omarchy-prompt/keys/anthropic",
        },
        "openai-api": {
            "type": "openai-compat",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-6.1-sol",
            "api_key_file": "~/.config/omarchy-prompt/keys/openai",
        },
        "gemini-api": {
            "type": "openai-compat",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": "gemini-4-hydrogen",
            "api_key_file": "~/.config/omarchy-prompt/keys/gemini",
        },
        "kimi-api": {
            "type": "openai-compat",
            "base_url": "https://api.moonshot.ai/v1",
            "model": "kimi-k3.1-pro",
            "api_key_file": "~/.config/omarchy-prompt/keys/kimi",
        },
        "deepseek-api": {
            "type": "openai-compat",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_file": "~/.config/omarchy-prompt/keys/deepseek",
        },
        "openrouter": {
            "type": "openai-compat",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "anthropic/claude-opus-5-5",
            "api_key_file": "~/.config/omarchy-prompt/keys/openrouter",
        },
        "ollama": {
            "type": "openai-compat",
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "qwen3.6:27b",
            "api_key_file": "",
            "enabled": False,
        },
        "s24-llama": {
            "type": "openai-compat",
            "base_url": "http://josmars-s24.taildab01d.ts.net:8080/v1",
            "model": "local",
            "api_key_file": "",
            "enabled": False,
        },
    },
}


def _merge(base, extra):
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _migrate(user):
    """1.0 wrote every default profile into the user file; 1.1 renamed them."""
    profiles = user.get("profiles")
    if isinstance(profiles, dict):
        if profiles.get("claude-cli", {}).get("type") == "claude-cli":
            profiles.pop("claude-cli")
        for old in ("anthropic", "openai", "gemini", "kimi", "deepseek"):
            prof = profiles.get(old)
            if isinstance(prof, dict) and prof.get("type") in ("anthropic", "openai-compat"):
                profiles.pop(old)
                profiles.setdefault(old + "-api", prof)
    if user.get("backend") == "claude-cli":
        user["backend"] = "auto"
    return user


def load():
    path = paths.config_path()
    user = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as fh:
                user = json.load(fh)
        except (OSError, ValueError):
            user = {}
    if not isinstance(user, dict):
        user = {}
    return _merge(DEFAULTS, _migrate(user))


def _read_user():
    path = paths.config_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_user(data):
    path = paths.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def ensure_file():
    """Write a starter config on first run so users can find and edit it."""
    path = paths.config_path()
    if not path.exists():
        save_user({"backend": DEFAULTS["backend"], "ui_lang": DEFAULTS["ui_lang"]})


def set_value(key, value):
    """Set a dotted key (e.g. 'profiles.ollama.model') in the user file."""
    data = _read_user()
    node = data
    parts = key.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"{key}: not an object")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass
    node[parts[-1]] = value
    save_user(data)


def remember(key, value):
    data = _migrate(_read_user())
    if data.get(key) != value:
        data[key] = value
        save_user(data)


def remember_target(target):
    remember("last_target", target)
